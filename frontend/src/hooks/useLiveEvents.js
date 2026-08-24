import { useEffect, useRef } from "react";
import { liveWebSocketUrl } from "../api";

/**
 * Connects to the backend's WS /live endpoint and calls onMessage(event) for
 * every {type, payload} pushed (new attendance entry / new alert). Reconnects
 * automatically (fixed 2s delay) if the connection drops - e.g. the backend
 * restarting mid-demo. onStatusChange (optional) is called with "connected" |
 * "disconnected" for a live status indicator in the UI.
 */
export function useLiveEvents(onMessage, onStatusChange) {
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;
  const onStatusChangeRef = useRef(onStatusChange);
  onStatusChangeRef.current = onStatusChange;

  useEffect(() => {
    let ws;
    let reconnectTimer;
    let cancelled = false;

    function connect() {
      ws = new WebSocket(liveWebSocketUrl());

      ws.onopen = () => {
        onStatusChangeRef.current?.("connected");
      };

      ws.onmessage = (event) => {
        try {
          onMessageRef.current(JSON.parse(event.data));
        } catch (err) {
          console.error("Failed to parse WS message:", err);
        }
      };

      ws.onclose = () => {
        onStatusChangeRef.current?.("disconnected");
        if (!cancelled) {
          reconnectTimer = setTimeout(connect, 2000);
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    return () => {
      cancelled = true;
      clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, []);
}
