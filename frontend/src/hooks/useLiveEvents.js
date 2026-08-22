import { useEffect, useRef } from "react";
import { liveWebSocketUrl } from "../api";

/**
 * Connects to the backend's WS /live endpoint and calls onMessage(event) for
 * every {type, payload} pushed (new attendance entry / new alert). Reconnects
 * automatically (fixed 2s delay) if the connection drops - e.g. the backend
 * restarting mid-demo.
 */
export function useLiveEvents(onMessage) {
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  useEffect(() => {
    let ws;
    let reconnectTimer;
    let cancelled = false;

    function connect() {
      ws = new WebSocket(liveWebSocketUrl());

      ws.onmessage = (event) => {
        try {
          onMessageRef.current(JSON.parse(event.data));
        } catch (err) {
          console.error("Failed to parse WS message:", err);
        }
      };

      ws.onclose = () => {
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
