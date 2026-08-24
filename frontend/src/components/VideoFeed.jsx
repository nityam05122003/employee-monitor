import { useState } from "react";
import { videoFeedUrl, loadCameraFromUrl, clearCamera } from "../api";
import { colorFor } from "../colors";

const RETRY_DELAY_MS = 2000;

// The backend streams multipart/x-mixed-replace JPEG frames - a plain <img>
// tag renders this natively as live video, no extra JS needed. BUT unlike
// the WebSocket (which has explicit reconnect logic), a plain <img> does NOT
// automatically reconnect if its connection drops (e.g. the backend
// restarts) - it just goes blank forever until something gives it a new src.
// onError + a "retry nonce" query param forces a fresh connection attempt.
export default function VideoFeed({ camera, onCameraChanged }) {
  const [retryNonce, setRetryNonce] = useState(0);
  const [url, setUrl] = useState("");
  const [loadStatus, setLoadStatus] = useState(null); // { type: "loading"|"error", message }

  const offline = camera.error || !camera.is_running;
  const isCustom = camera.kind === "custom";
  const accent = colorFor(camera.id);

  function handleError() {
    setTimeout(() => setRetryNonce((n) => n + 1), RETRY_DELAY_MS);
  }

  async function handleLoadUrl(e) {
    e.preventDefault();
    if (!url.trim()) return;
    setLoadStatus({ type: "loading", message: "Downloading video - this can take a moment depending on its length..." });
    try {
      const updated = await loadCameraFromUrl(camera.id, url.trim());
      setLoadStatus(updated.error ? { type: "error", message: updated.error } : null);
      if (!updated.error) setUrl("");
      onCameraChanged?.();
    } catch (err) {
      setLoadStatus({ type: "error", message: err.message });
    }
  }

  async function handleClear() {
    setLoadStatus(null);
    try {
      await clearCamera(camera.id);
      onCameraChanged?.();
    } catch (err) {
      setLoadStatus({ type: "error", message: err.message });
    }
  }

  return (
    <div className="panel camera-panel" style={{ "--accent-color": accent }}>
      <div className="camera-panel-head">
        <h2>{camera.label}</h2>
        <span className={`camera-badge ${offline ? "down" : "live"}`}>
          {offline ? "Offline" : "Live"}
        </span>
      </div>
      <div className="video-frame">
        {offline ? (
          <div className="camera-offline">
            <p>{isCustom && !camera.error ? "No video loaded yet" : "Camera unavailable"}</p>
            {camera.error && <p className="camera-error-detail">{camera.error}</p>}
          </div>
        ) : (
          <img
            key={retryNonce}
            className="video-feed"
            src={`${videoFeedUrl(camera.id)}?retry=${retryNonce}`}
            alt={`Live feed from ${camera.label} with face detection boxes`}
            onError={handleError}
          />
        )}
      </div>
      {isCustom && (
        <form className="custom-url-form" onSubmit={handleLoadUrl}>
          <input
            type="text"
            placeholder="Paste a video URL (YouTube, direct .mp4 link...)"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            disabled={loadStatus?.type === "loading"}
          />
          <button type="submit" disabled={loadStatus?.type === "loading"}>
            {loadStatus?.type === "loading" ? "Loading..." : "Load Video"}
          </button>
          {camera.is_running && (
            <button type="button" className="clear-btn" onClick={handleClear}>
              Clear
            </button>
          )}
        </form>
      )}
      {loadStatus && <p className={`status-message status-${loadStatus.type}`}>{loadStatus.message}</p>}
    </div>
  );
}
