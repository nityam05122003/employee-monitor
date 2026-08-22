"""
Thin wrapper around InsightFace's FaceAnalysis (buffalo_l model): detection +
512-d embedding extraction, plus cosine similarity matching.

Loaded once at app startup (see main.py) since it's relatively expensive
(loads several ONNX models into memory, and downloads them on first run).
"""
import logging
import threading

import numpy as np

from app.config import settings

logger = logging.getLogger("face_engine")


class FaceEngine:
    def __init__(self):
        self._app = None
        # InsightFace's ONNX sessions are used from both the recognition
        # background thread and the enrollment request thread; serialize
        # access to keep this simple and safe rather than relying on
        # onnxruntime's concurrent-Run guarantees.
        self._lock = threading.Lock()

    def load(self, model_name: str):
        # Imported here (not at module level) so the app can start up and
        # report a clear config-level error even if insightface itself fails
        # to import for some reason.
        from insightface.app import FaceAnalysis

        logger.info(
            f"Loading InsightFace model '{model_name}'. On first run this "
            f"downloads ~300MB+ of model weights from GitHub - this can "
            f"take a few minutes depending on your connection."
        )
        app = FaceAnalysis(name=model_name, providers=["CPUExecutionProvider"])
        # ctx_id=-1 forces CPU (no CUDA GPU available on this machine).
        # det_size/det_thresh are configurable (DETECTION_SIZE/DET_THRESH) -
        # raise det_size and lower det_thresh for CCTV footage with small,
        # far-away faces; the defaults suit a close laptop webcam.
        app.prepare(
            ctx_id=-1,
            det_size=(settings.DETECTION_SIZE, settings.DETECTION_SIZE),
            det_thresh=settings.DET_THRESH,
        )
        self._app = app
        logger.info(
            f"InsightFace model loaded and ready "
            f"(det_size={settings.DETECTION_SIZE}, det_thresh={settings.DET_THRESH})."
        )

    @property
    def ready(self) -> bool:
        return self._app is not None

    def detect(self, frame_bgr):
        """Returns a list of insightface Face objects (each with .bbox,
        .normed_embedding, .det_score) for all faces found in the frame."""
        if self._app is None:
            return []
        with self._lock:
            return self._app.get(frame_bgr)

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        # normed_embedding vectors from insightface are already L2-normalized,
        # so a plain dot product IS the cosine similarity.
        return float(np.dot(a, b))


# Single shared instance - loaded once at startup, read from everywhere else.
face_engine = FaceEngine()
