# Employee Monitor (prototype)

Multi-camera employee monitoring (laptop webcam, WiFi/network CCTV cameras,
and/or pre-recorded video files - all running simultaneously): real-time
face recognition (InsightFace `buffalo_l`), automatic attendance logging,
alerts on unrecognized faces, and a live React dashboard with one video
panel per camera. Local-only prototype - no auth, no Docker, SQLite for
storage.

Attendance/idle-time/alerts are tracked per PERSON, not per camera - if an
employee is seen on any one of the configured cameras, that counts; a person
being active on Camera A is never overridden by Camera B not seeing them.

## Stack

- **Backend**: Python + FastAPI, SQLite (via SQLAlchemy), WebSockets, OpenCV + InsightFace
- **Frontend**: React (Vite), plain CSS
- **Video to browser**: MJPEG stream (`<img>` tag, no WebRTC)

## One-time setup

### Backend

```bash
cd backend
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

First run will also download the InsightFace `buffalo_l` model (~300MB) from
GitHub the first time the server starts - this needs an internet connection
and can take a few minutes.

### Frontend

```bash
cd frontend
npm install
```

## Running it

Two terminals:

```bash
# Terminal 1 - backend (http://localhost:8003)
cd backend
./run.sh

# Terminal 2 - frontend (http://localhost:5173)
cd frontend
npm run dev
```

Open **http://localhost:5173** for the dashboard (one video panel per configured camera), or hit a specific camera's feed directly at **http://localhost:8003/video_feed/{id}** (see `GET /cameras` for valid ids).

Note: the backend runs on port **8003**, not the more common 8000/8001 -
those were already in use by other local services on the machine this was
built on. Change the port in `backend/run.sh` (and `API_BASE` in
`frontend/src/api.js`) if you need to.

## Enrolling employees

Either use the "Enroll Employee" form in the dashboard, or run the CLI:

```bash
cd backend
.venv/bin/python scripts/enroll_cli.py
```

Both work the same way: the **backend** samples a few frames from a live
camera feed over ~4 seconds and stores a face embedding per shot. By default
it uses the first running camera; to enroll from a specific one, pass
`source_id` in the `/enroll` request body (matching an id from `GET
/cameras`). Look directly at that camera when enrolling.

## Tuning

All tunables live in `backend/app/config.py` (override via `backend/.env`,
see `.env.example`):

- `RECOGNITION_THRESHOLD` (default 0.45) - cosine similarity match threshold. Lower it if real employees keep showing as "unknown"; raise it if strangers get matched.
- `DETECTION_INTERVAL_SEC` (default 0.3) - how often frames are analyzed (~3fps). Raise for less CPU usage, lower for snappier detection.
- `DETECTION_SIZE` / `DET_THRESH` (default 640 / 0.5) - detector input size and minimum confidence. See "Using a WiFi/CCTV camera" below for far-away-face tuning.
- `UNKNOWN_ALERT_SECONDS` / `ALERT_COOLDOWN_SECONDS` - how long an unknown face must persist before alerting, and the minimum gap between repeat alerts.
- `HEAD_YAW_THRESHOLD_DEG` / `HEAD_PITCH_THRESHOLD_DEG` (default 35/35) - how far a recognized employee's head can turn away from the camera before counting as "distracted" (idle). Laptop webcams sit below eye level, so normal screen-facing pitch is already noticeably non-zero - lower these if idle detection feels too lenient, raise them if normal posture keeps triggering it.
- `IDLE_ALERT_SECONDS` / `IDLE_ALERT_COOLDOWN_SECONDS` (default 60/120) - how long an employee must be continuously idle (away from camera OR facing away) before an idle alert fires, and the minimum gap between repeat idle alerts for the same employee.

### Idle / "relaxing" detection (heuristic, not true activity tracking)

Every checked-in employee's `idle_seconds` (shown in the attendance table) accumulates whenever they're either not visible to the camera at all ("away") or visible but facing away from the screen beyond the head-pose thresholds above ("distracted" - e.g. looking down at a phone). Once continuous idle time crosses `IDLE_ALERT_SECONDS`, an `employee_idle` alert fires (same alerts panel as unauthorized-face alerts, distinguished by type/color).

**Important limitation**: a webcam can only tell you whether a face is present and which way it's pointing - it cannot tell if someone is actually working. Reading a physical document, looking at a second monitor, or talking to a coworker will all register as "distracted." Tune the thresholds above, or treat this purely as a rough presence/attention proxy rather than a productivity measurement.

## Configuring cameras (webcam + CCTV + video files, all at once)

Every camera in `CAMERA_SOURCES` (`backend/.env`, a JSON array) runs
simultaneously - each gets its own capture thread and its own
`/video_feed/{id}` panel on the dashboard. A source can be a local webcam
index, an RTSP/network CCTV URL, or a path to a video file (handy for
testing/demos - it loops automatically). Mix and match freely:

```bash
CAMERA_SOURCES=[{"id":"laptop","label":"Laptop Webcam","source":"0"},{"id":"cctv","label":"Office CCTV","source":"rtsp://user:pass@192.168.1.50:554/stream1"},{"id":"custom","label":"Custom Video","source":"","kind":"custom"}]
```

If a source fails to start (wrong RTSP URL, camera unreachable, etc.) it
just shows "Camera unavailable" on its own panel with the error message -
the other cameras keep working normally. Check `GET /cameras` for each
source's live status.

### Testing with any video (no physical camera needed)

A `"kind":"custom"` entry (empty `source`) shows a **paste-a-video-URL** box
on its dashboard panel instead of a video, at any time - YouTube links and
most direct video URLs both work. Behind the scenes: `POST
/cameras/{id}/load_url` (body `{"url": "..."}`) downloads the video via
`yt-dlp` into `backend/data/custom_videos/{id}.*`, then points that
camera at the downloaded file - detection starts on it automatically. You
can paste a new URL into the same box at any time to swap the video out.

Requires `yt-dlp` on the machine running the backend:
```bash
brew install yt-dlp
```

**Finding your camera's RTSP URL**: this varies by brand - check the
camera's app/web settings (usually under "Advanced," "Network," or "RTSP")
for the exact path. Some common patterns:

- Hikvision: `rtsp://user:pass@<ip>:554/Streaming/Channels/101`
- Dahua: `rtsp://user:pass@<ip>:554/cam/realmonitor?channel=1&subtype=0`
- Reolink: `rtsp://user:pass@<ip>:554/h264Preview_01_main`
- Generic ONVIF: `rtsp://user:pass@<ip>:554/live/ch0` (or similar)

The camera and the machine running this backend both need to be on the same
network (or otherwise routable to each other) - a CCTV camera on its own
isolated VLAN/subnet won't be reachable.

**Test the URL directly before wiring it in**, so you know whether a
problem is the URL/network vs. something else:

```bash
cd backend
.venv/bin/python -c "
import cv2
cap = cv2.VideoCapture('rtsp://user:pass@192.168.1.50:554/stream1', cv2.CAP_FFMPEG)
print('opened:', cap.isOpened())
print('frame ok:', cap.read()[0])
"
```

**Network cameras drop connections more than a local webcam** (WiFi hiccups,
camera reboots) - the backend automatically detects a stalled stream and
reconnects after `CAMERA_RECONNECT_AFTER_SEC` (default 5s) with no frames.

**Far-away/small faces**: CCTV cameras are usually mounted farther from
people than a laptop webcam, so faces occupy far fewer pixels. Two knobs
help (both in `.env`):
- `DETECTION_SIZE` - raise from 640 to 960 or 1280 for higher-resolution
  detection (slower per frame, better at finding small/far faces).
- `DET_THRESH` - lower from 0.5 to ~0.3 to catch more marginal/blurry
  detections (more false positives as a tradeoff).

**Be realistic about accuracy at a distance**: this is a genuine hardware
limitation, not something pure config can fully solve - a face that's only
20-30 pixels across simply doesn't carry enough detail for a confident
`arcface` embedding, no matter how the detector is tuned. Expect recognition
confidence (and `RECOGNITION_THRESHOLD` headroom) to be noticeably lower for
far-away faces than for a close laptop webcam shot. If accuracy at distance
matters a lot, a higher-resolution camera and/or a narrower field of view
pointed at the area people actually pass through will help more than
software tuning alone.

## Common issues

- **Webcam not detected / blank video feed**: check System Settings ->
  Privacy & Security -> Camera and make sure your terminal/IDE has access.
  Also check no other app (Zoom, FaceTime) is using the camera.
- **One camera shows "Camera unavailable"**: check its `error` field via
  `GET /cameras` - almost always a wrong RTSP path for CCTV (see "Configuring
  cameras" above for the direct `cv2.VideoCapture` test script and common URL
  patterns by brand). The other cameras keep working regardless.
- **Nobody enrolled yet**: recognition still runs, everyone just shows as
  "unknown (no employees enrolled)" - enroll yourself first.
- **Model download fails on first run**: needs internet access to fetch
  `buffalo_l` from GitHub once; after that it's cached in `~/.insightface/`.
- **Port 8003 already in use**: something else is running on it, or the
  server is already running - check `lsof -iTCP:8003 -sTCP:LISTEN` and
  `ps aux | grep uvicorn` before starting another instance (running two
  backend instances against the same SQLite file will create duplicate
  attendance records).

## What's NOT included (by design)

Cloud deployment/Docker, user authentication, a mobile app, and
analytics/reporting beyond today's attendance + alerts list - all explicitly
out of scope for this prototype.
