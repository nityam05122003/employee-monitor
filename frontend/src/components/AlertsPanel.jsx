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

export default function AlertsPanel({ alerts, onAcknowledge, cameras = [] }) {
  return (
    <div className="panel">
      <h2>Alerts</h2>
      {alerts.length === 0 ? (
        <p className="empty-state">No alerts.</p>
      ) : (
        <ul className="alerts-list">
          {alerts.map((a) => {
            const cam = cameraLabel(cameras, a.source_id);
            return (
              <li key={a.id} className={`alert-item alert-${a.status} alert-type-${a.alert_type}`}>
                {a.snapshot_path && (
                  <img className="alert-thumb" src={snapshotUrl(a.snapshot_path)} alt={alertHeadline(a)} />
                )}
                <div className="alert-info">
                  <div className="alert-headline">{alertHeadline(a)}</div>
                  <div className="alert-time">
                    {new Date(a.timestamp).toLocaleString()}
                    {cam && <span className="muted"> - {cam}</span>}
                  </div>
                  <div className="alert-status">{a.status}</div>
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
