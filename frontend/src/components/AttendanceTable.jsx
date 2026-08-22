function formatTime(iso) {
  return new Date(iso).toLocaleTimeString();
}

function formatIdle(seconds) {
  const total = Math.round(seconds || 0);
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  if (mins === 0) return `${secs}s`;
  return `${mins}m ${secs}s`;
}

function cameraLabel(cameras, sourceId) {
  if (!sourceId) return "-";
  return cameras.find((c) => c.id === sourceId)?.label || sourceId;
}

export default function AttendanceTable({ records, cameras = [] }) {
  return (
    <div className="panel">
      <h2>Today's Attendance</h2>
      <p className="panel-hint">
        Idle time = away from camera or looking away from the screen (approximate).
      </p>
      {records.length === 0 ? (
        <p className="empty-state">No one has been recognized yet today.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Employee</th>
              <th>Entry</th>
              <th>Last Seen</th>
              <th>Idle Time</th>
              <th>Camera</th>
            </tr>
          </thead>
          <tbody>
            {records.map((r) => (
              <tr key={r.employee_id}>
                <td>
                  {r.name} <span className="muted">({r.employee_code})</span>
                </td>
                <td>{formatTime(r.entry_time)}</td>
                <td>{formatTime(r.last_seen_time)}</td>
                <td>{formatIdle(r.idle_seconds)}</td>
                <td>{cameraLabel(cameras, r.last_seen_source)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
