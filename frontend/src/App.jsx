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

  useLiveEvents((event) => {
    if (event.type === "attendance") {
      loadAttendance();
    } else if (event.type === "alert") {
      setAlerts((prev) => [event.payload, ...prev]);
    }
  });

  async function handleAcknowledge(alertId) {
    const updated = await acknowledgeAlert(alertId);
    setAlerts((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Employee Monitor</h1>
      </header>
      <main className="dashboard">
        <div className="column">
          <div className="camera-grid">
            {cameras.map((cam) => (
              <VideoFeed key={cam.id} camera={cam} />
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
