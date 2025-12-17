/**
 * React hook for streaming UI components from the backend
 *
 * Phase 2: Full streaming with merge, remove, reconnection, and error handling.
 */
import { useState, useEffect, useRef } from 'react';
import type { DynamicUIPayload } from './types';

interface UIEvent {
  type: 'ui' | 'remove-ui';
  id: string;
  graph_name?: string;
  component_name?: string;
  props?: any;
  merge?: boolean;
}

interface StreamingComponent extends DynamicUIPayload {
  id: string;
}

export function useUIStream(apiUrl: string, sessionId: string) {
  const [components, setComponents] = useState<StreamingComponent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttempts = useRef(0);

  useEffect(() => {
    if (!sessionId) {
      console.warn('[useUIStream] No session ID provided');
      return;
    }

    const connect = () => {
      const streamUrl = `${apiUrl}/ui/stream?session=${sessionId}`;
      console.log('[useUIStream] Connecting to:', streamUrl);

      const eventSource = new EventSource(streamUrl);
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        console.log('[useUIStream] ✅ Connected');
        setConnected(true);
        setError(null);
        reconnectAttempts.current = 0;
      };

      eventSource.onmessage = (e) => {
        try {
          const evt: UIEvent = JSON.parse(e.data);

          if (evt.type === 'ui') {
            console.log('[useUIStream] 📡 Received UI event:', evt);

            // Validate required fields for new components or replacements
            if (!evt.merge && (!evt.graph_name || !evt.component_name)) {
              console.error('[useUIStream] ⚠️ Skipping invalid UI event - missing graph_name or component_name:', evt);
              return;
            }

            setComponents(prev => {
              // Check if component with this ID exists
              const existingIdx = prev.findIndex(c => c.id === evt.id);

              if (existingIdx >= 0) {
                // Component exists
                if (evt.merge) {
                  // Merge props
                  const updated = [...prev];
                  const oldProps = updated[existingIdx].props;
                  const newProps = { ...oldProps, ...evt.props };
                  updated[existingIdx] = {
                    ...updated[existingIdx],
                    props: newProps,
                  };
                  console.log('[useUIStream] 🔄 Merged component:', evt.id, 'Old props:', oldProps, 'New props:', newProps);
                  return updated;
                } else {
                  // Replace entire component
                  const updated = [...prev];
                  updated[existingIdx] = {
                    id: evt.id,
                    graph_name: evt.graph_name!,
                    component_name: evt.component_name!,
                    props: evt.props || {},
                  };
                  console.log('[useUIStream] ♻️ Replaced component:', evt.id, 'New props:', evt.props);
                  return updated;
                }
              } else {
                // New component (skeleton!)
                const newComponent = {
                  id: evt.id,
                  graph_name: evt.graph_name!,
                  component_name: evt.component_name!,
                  props: evt.props || {},
                };
                console.log('[useUIStream] ➕ Added NEW component (skeleton?):', evt.id, 'Props:', evt.props);
                return [...prev, newComponent];
              }
            });
          } else if (evt.type === 'remove-ui') {
            console.log('[useUIStream] 🗑️ Removing component:', evt.id);
            setComponents(prev => prev.filter(c => c.id !== evt.id));
          }
        } catch (err) {
          console.error('[useUIStream] Failed to parse event:', err);
        }
      };

      eventSource.onerror = (err) => {
        console.error('[useUIStream] ❌ Connection error:', err);
        setConnected(false);
        setError('Connection lost. Reconnecting...');
        eventSource.close();

        // Auto-reconnect with exponential backoff
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000);
        reconnectAttempts.current++;

        console.log(`[useUIStream] 🔄 Reconnecting in ${delay}ms (attempt ${reconnectAttempts.current})...`);

        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, delay);
      };
    };

    connect();

    return () => {
      console.log('[useUIStream] 🔌 Disconnecting');
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [apiUrl, sessionId]);

  return { components, connected, error };
}
