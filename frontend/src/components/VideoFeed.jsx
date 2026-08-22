import { useState } from "react";
import { videoFeedUrl } from "../api";

const RETRY_DELAY_MS = 2000;

// The backend streams multipart/x-mixed-replace JPEG frames - a plain <img>
// tag renders this natively as live video, no extra JS needed. BUT unlike
// the WebSocket (which has explicit reconnect logic), a plain <img> does NOT
// automatically reconnect if its connection drops (e.g. the backend
// restarts) - it just goes blank forever until something gives it a new src.
// onError + a "retry nonce" query param forces a fresh connection attempt.
export default function VideoFeed({ camera }) {
  const [retryNonce, setRetryNonce] = useState(0);
  const offline = camera.error || !camera.is_running;

  function handleError() {
    setTimeout(() => setRetryNonce((n) => n + 1), RETRY_DELAY_MS);
  }

  return (
    <div className="panel">
      <h2>{camera.label}</h2>
      {offline ? (
        <div className="camera-offline">
          <p>Camera unavailable</p>
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
  );
}
