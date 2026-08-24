import { useCallback, useEffect, useState } from "react";
import VideoFeed from "./components/VideoFeed";
import AttendanceTable from "./components/AttendanceTable";
import AlertsPanel from "./components/AlertsPanel";
import EnrollForm from "./components/EnrollForm";
import { fetchAttendanceToday, fetchAlerts, fetchCameras, acknowledgeAlert } from "./api";
import { useLiveEvents } from "./hooks/useLiveEvents";
import "./App.css";

export default function App() {
  const [attendance, setAttendance] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [cameras, setCameras] = useState([]);
  const [liveStatus, setLiveStatus] = useState("connecting");

  const loadAttendance = useCallback(() => {
    fetchAttendanceToday().then(setAttendance).catch(console.error);
  }, []);

  const loadAlerts = useCallback(() => {
    fetchAlerts().then(setAlerts).catch(console.error);
  }, []);

  const loadCameras = useCallback(() => {
    fetchCameras().then(setCameras).catch(console.error);
  }, []);

  useEffect(() => {
    loadAttendance();
    loadAlerts();
    loadCameras();
    // WS only pushes on brand-new entries (see backend/app/recognition_service.py),
    // so poll periodically too - this keeps "last seen"/idle time visibly advancing,
    // and picks up a camera reconnecting after a failure.
    const interval = setInterval(() => {
      loadAttendance();
      loadCameras();
    }, 5000);
    return () => clearInterval(interval);
  }, [loadAttendance, loadAlerts, loadCameras]);

  useLiveEvents(
    (event) => {
      if (event.type === "attendance") {
        loadAttendance();
      } else if (event.type === "alert") {
        setAlerts((prev) => [event.payload, ...prev]);
      }
    },
    setLiveStatus,
  );

  async function handleAcknowledge(alertId) {
    const updated = await acknowledgeAlert(alertId);
    setAlerts((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-logo">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
            <path d="M12 12a4 4 0 100-8 4 4 0 000 8zM4 20c0-3.5 3.5-6 8-6s8 2.5 8 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        <h1>Employee Monitor</h1>
        <div className={`live-indicator ${liveStatus === "connected" ? "" : "offline"}`}>
          <span className="live-dot" />
          {liveStatus === "connected" ? "Live" : "Reconnecting..."}
        </div>
      </header>
      <main className="dashboard">
        <div className="column">
          <div className="camera-grid">
            {cameras.map((cam) => (
              <VideoFeed key={cam.id} camera={cam} onCameraChanged={loadCameras} />
            ))}
          </div>
          <EnrollForm onEnrolled={loadAttendance} />
        </div>
        <div className="column">
          <AttendanceTable records={attendance} cameras={cameras} />
          <AlertsPanel alerts={alerts} onAcknowledge={handleAcknowledge} cameras={cameras} />
        </div>
      </main>
    </div>
  );
}
