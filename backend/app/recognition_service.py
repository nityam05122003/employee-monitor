"""
RecognitionWorker: single background thread that, at a throttled rate
(settings.DETECTION_INTERVAL_SEC, ~2-5fps), polls EVERY configured camera
source (camera_manager.py - laptop webcam, CCTV, video files, all running
simultaneously) in one synchronized "round": runs InsightFace detection +
embedding + matching on each camera's latest frame, draws boxes/labels onto
that camera's own annotated frame (for its own /video_feed/{id}), and then
does ONE combined attendance/idle/alert bookkeeping pass per round.

Why one combined pass instead of fully independent per-camera loops:
attendance/idle/alerts are about a PERSON, not a camera. If employee X is
active on Camera A, Camera B "not seeing" them in the same round must NOT
independently mark them idle - only a combined view across all cameras this
round can safely decide "were they active anywhere" before updating idle
state, so idle/alert bookkeeping happens once per round, after every camera
has been polled.
"""
import json
import logging
import threading
import time

import cv2
import numpy as np

from app.config import settings
from app.camera_manager import camera_manager
from app.face_engine import face_engine
from app.database import SessionLocal
from app.models import Employee, FaceEmbedding
from app import attendance_service
from app.alert_service import alert_tracker
from app.idle_service import idle_tracker
from app.ws_manager import ws_manager

logger = logging.getLogger("recognition")

BOX_COLOR_KNOWN = (0, 200, 0)         # green (BGR) - recognized + facing camera
BOX_COLOR_DISTRACTED = (0, 165, 255)  # orange (BGR) - recognized but looking away
BOX_COLOR_UNKNOWN = (0, 0, 255)       # red (BGR) - unrecognized face


class RecognitionWorker:
    def __init__(self):
        self._known_lock = threading.Lock()
        self._known = []  # list of (employee_id, name, embedding: np.ndarray)

        self._running = False
        self._thread = None

        self.reload_known_embeddings()

    def reload_known_embeddings(self):
        """(Re)loads all enrolled face embeddings from the DB into memory.
        Called at startup and again after every successful enrollment."""
        db = SessionLocal()
        try:
            rows = (
                db.query(FaceEmbedding, Employee)
                .join(Employee, FaceEmbedding.employee_id == Employee.id)
                .all()
            )
            known = [
                (emp.id, emp.name, np.array(json.loads(fe.embedding), dtype=np.float32))
                for fe, emp in rows
            ]
        finally:
            db.close()

        with self._known_lock:
            self._known = known
        n_employees = len({e[0] for e in known})
        logger.info(f"Loaded {len(known)} face embedding(s) for {n_employees} employee(s).")

    def _match(self, embedding: np.ndarray):
        """Returns (employee_id, name, score) if the best match clears the
        recognition threshold, else (None, None, score) - score is None if
        there are no enrolled employees at all yet."""
        with self._known_lock:
            known = self._known

        if not known:
            return None, None, None

        best_score = -1.0
        best = None
        for emp_id, name, vec in known:
            score = face_engine.cosine_similarity(embedding, vec)
            if score > best_score:
                best_score = score
                best = (emp_id, name)

        if best_score >= settings.RECOGNITION_THRESHOLD:
            return best[0], best[1], best_score
        return None, None, best_score

    @staticmethod
    def _is_facing_camera(face) -> bool:
        """Heuristic only - see idle_service.py docstring for caveats.
        insightface's Face.pose is [pitch, yaw, roll] in degrees, derived
        from the 3D landmark model. If unavailable, don't penalize."""
        pose = getattr(face, "pose", None)
        if pose is None:
            return True
        pitch, yaw, roll = pose
        return (
            abs(yaw) <= settings.HEAD_YAW_THRESHOLD_DEG
            and abs(pitch) <= settings.HEAD_PITCH_THRESHOLD_DEG
        )

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("Recognition loop started.")

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        logger.info("Recognition loop stopped.")

    @property
    def is_running(self) -> bool:
        return self._running

    def _process_camera(self, cam, active_employee_ids, seen_employee_source, seen_employee_frame):
        """Runs detection on one camera's latest frame, draws its annotated
        frame, and updates the round's shared per-employee tracking dicts.
        Returns (unknown_seen_on_this_camera, this_camera_annotated_frame_or_None)."""
        frame = cam.worker.get_latest_frame()
        if frame is None:
            return False, None

        faces = face_engine.detect(frame)
        annotated = frame.copy()
        unknown_seen = False
        recorded_this_tick = set()

        for face in faces:
            x1, y1, x2, y2 = face.bbox.astype(int)
            emp_id, name, score = self._match(face.normed_embedding)

            if emp_id is not None:
                facing_camera = self._is_facing_camera(face)
                if facing_camera:
                    active_employee_ids.add(emp_id)
                    label = f"{name} ({score:.2f})"
                    color = BOX_COLOR_KNOWN
                else:
                    label = f"{name} ({score:.2f}) [away from screen]"
                    color = BOX_COLOR_DISTRACTED

                if emp_id not in recorded_this_tick:
                    recorded_this_tick.add(emp_id)
                    seen_employee_source.setdefault(emp_id, cam.id)
                    seen_employee_frame.setdefault(emp_id, annotated)
            elif score is None:
                label = "unknown (no employees enrolled)"
                color = BOX_COLOR_UNKNOWN
                unknown_seen = True
            else:
                label = f"unknown ({score:.2f})"
                color = BOX_COLOR_UNKNOWN
                unknown_seen = True

            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            cv2.putText(
                annotated, label, (x1, max(y1 - 10, 15)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2,
            )

        cv2.putText(
            annotated, cam.label, (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2,
        )
        cam.set_annotated(annotated)
        return unknown_seen, annotated

    def _loop(self):
        while self._running:
            tick_start = time.time()

            active_employee_ids = set()    # facing camera on >=1 source this round
            seen_employee_source = {}      # emp_id -> id of first camera that saw them this round
            seen_employee_frame = {}       # emp_id -> that camera's annotated frame (for idle-alert snapshots)
            unknown_seen_any = False
            unknown_source_id = None
            unknown_snapshot_frame = None

            for cam in camera_manager.sources:
                if not cam.is_running:
                    continue
                unknown_here, annotated = self._process_camera(
                    cam, active_employee_ids, seen_employee_source, seen_employee_frame,
                )
                if unknown_here:
                    unknown_seen_any = True
                    unknown_source_id = cam.id
                    unknown_snapshot_frame = annotated

            # --- combined per-person attendance bookkeeping (once per round) ---
            for emp_id, source_id in seen_employee_source.items():
                new_entry = attendance_service.record_sighting(emp_id, source_id=source_id)
                if new_entry is not None:
                    ws_manager.broadcast({"type": "attendance", "payload": new_entry})

            # --- combined per-person idle tracking (once per round, across ALL cameras) ---
            for emp_id in attendance_service.get_checked_in_employee_ids_today():
                is_idle = emp_id not in active_employee_ids
                if not is_idle:
                    reason = None
                elif emp_id in seen_employee_source:
                    reason = "distracted"  # seen, but not facing any camera
                else:
                    reason = "away"        # not seen on any camera at all

                idle_alert = idle_tracker.report_tick(
                    emp_id, is_idle, reason, settings.DETECTION_INTERVAL_SEC,
                    frame_for_snapshot=seen_employee_frame.get(emp_id),
                    source_id=seen_employee_source.get(emp_id),
                )
                if idle_alert is not None:
                    ws_manager.broadcast({"type": "alert", "payload": idle_alert})

            # --- unauthorized (unrecognized) face alert (once per round) ---
            alert = alert_tracker.report_tick(unknown_seen_any, unknown_snapshot_frame, unknown_source_id)
            if alert is not None:
                ws_manager.broadcast({"type": "alert", "payload": alert})

            elapsed = time.time() - tick_start
            time.sleep(max(0.0, settings.DETECTION_INTERVAL_SEC - elapsed))


# Single shared instance.
recognition_worker = RecognitionWorker()
