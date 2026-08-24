import { snapshotUrl } from "../api";

function alertHeadline(a) {
  if (a.alert_type === "employee_idle") {
    const who = a.employee_name ? `${a.employee_name} (${a.employee_code})` : "An employee";
    return `${who} has been idle/away`;
  }
  return "Unrecognized person detected";
}

function cameraLabel(cameras, sourceId) {
  if (!sourceId) return null;
  return cameras.find((c) => c.id === sourceId)?.label || sourceId;
}

function relativeTime(iso) {
  const diffSec = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (diffSec < 60) return "just now";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  return `${Math.floor(diffHr / 24)}d ago`;
}

function AlertIcon({ type }) {
  if (type === "employee_idle") {
    return (
      <svg width="17" height="17" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2" />
        <path d="M12 7v5l3 3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none">
      <path d="M12 9v4M12 17h.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <path d="M10.3 3.9L2.7 17a1.5 1.5 0 001.3 2.3h16a1.5 1.5 0 001.3-2.3L13.7 3.9a1.5 1.5 0 00-2.6 0z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
    </svg>
  );
}

export default function AlertsPanel({ alerts, onAcknowledge, cameras = [] }) {
  const newCount = alerts.filter((a) => a.status === "new").length;

  return (
    <div className="panel" style={{ "--accent-color": "#ea580c" }}>
      <h2>
        Alerts
        {newCount > 0 && <span className="panel-count">{newCount}</span>}
      </h2>
      {alerts.length === 0 ? (
        <p className="empty-state">No alerts.</p>
      ) : (
        <ul className="alerts-list">
          {alerts.map((a) => {
            const cam = cameraLabel(cameras, a.source_id);
            return (
              <li key={a.id} className={`alert-item alert-${a.status} alert-type-${a.alert_type}`}>
                {a.snapshot_path ? (
                  <img className="alert-thumb" src={snapshotUrl(a.snapshot_path)} alt={alertHeadline(a)} />
                ) : (
                  <span className="alert-icon">
                    <AlertIcon type={a.alert_type} />
                  </span>
                )}
                <div className="alert-info">
                  <div className="alert-headline">{alertHeadline(a)}</div>
                  <div className="alert-time">
                    {relativeTime(a.timestamp)} - {new Date(a.timestamp).toLocaleString()}
                    {cam && <span className="muted"> - {cam}</span>}
                  </div>
                  <span className="alert-status">{a.status}</span>
                </div>
                {a.status === "new" && (
                  <button onClick={() => onAcknowledge(a.id)}>Acknowledge</button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
