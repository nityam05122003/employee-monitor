import { useState } from "react";
import { enrollEmployee } from "../api";

// "Capture Face" doesn't use the browser's camera - the backend already owns
// the one physical webcam (see backend/app/camera.py), so this just tells
// the backend to sample a few shots from its already-running feed.
export default function EnrollForm({ onEnrolled }) {
  const [employeeCode, setEmployeeCode] = useState("");
  const [name, setName] = useState("");
  const [status, setStatus] = useState(null); // { type: "loading" | "success" | "error", message }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!employeeCode.trim() || !name.trim()) return;

    setStatus({ type: "loading", message: "Capturing face shots - look at the camera..." });
    try {
      const result = await enrollEmployee(employeeCode.trim(), name.trim());
      setStatus({
        type: "success",
        message: `Enrolled ${result.name}: ${result.embeddings_captured}/${result.shots_attempted} shots captured.`,
      });
      setEmployeeCode("");
      setName("");
      onEnrolled?.();
    } catch (err) {
      setStatus({ type: "error", message: err.message });
    }
  }

  const loading = status?.type === "loading";

  return (
    <div className="panel" style={{ "--accent-color": "#7c3aed" }}>
      <h2>Enroll Employee</h2>
      <form onSubmit={handleSubmit} className="enroll-form">
        <input
          type="text"
          placeholder="Employee code (e.g. EMP002)"
          value={employeeCode}
          onChange={(e) => setEmployeeCode(e.target.value)}
          disabled={loading}
        />
        <input
          type="text"
          placeholder="Full name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={loading}
        />
        <button type="submit" disabled={loading}>
          {loading ? "Capturing..." : "Capture Face"}
        </button>
      </form>
      {status && <p className={`status-message status-${status.type}`}>{status.message}</p>}
    </div>
  );
}
