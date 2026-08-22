// All backend calls in one place. Change API_BASE if the backend isn't on
// localhost:8003 (see backend/run.sh).
const API_BASE = "http://localhost:8003";

async function handleResponse(res) {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      // response wasn't JSON - keep statusText
    }
    throw new Error(detail);
  }
  return res.json();
}

export function videoFeedUrl(sourceId) {
  return sourceId ? `${API_BASE}/video_feed/${sourceId}` : `${API_BASE}/video_feed`;
}

export async function fetchCameras() {
  const res = await fetch(`${API_BASE}/cameras`);
  return handleResponse(res);
}

export function snapshotUrl(filename) {
  return `${API_BASE}/snapshots/${filename}`;
}

export function liveWebSocketUrl() {
  return API_BASE.replace(/^http/, "ws") + "/live";
}

export async function fetchAttendanceToday() {
  const res = await fetch(`${API_BASE}/attendance/today`);
  return handleResponse(res);
}

export async function fetchAlerts() {
  const res = await fetch(`${API_BASE}/alerts`);
  return handleResponse(res);
}

export async function acknowledgeAlert(alertId) {
  const res = await fetch(`${API_BASE}/alerts/${alertId}/ack`, { method: "POST" });
  return handleResponse(res);
}

export async function enrollEmployee(employeeCode, name) {
  const res = await fetch(`${API_BASE}/enroll`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ employee_code: employeeCode, name }),
  });
  return handleResponse(res);
}
