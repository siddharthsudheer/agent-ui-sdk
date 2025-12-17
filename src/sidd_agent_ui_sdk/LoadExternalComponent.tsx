/**
 * LoadExternalComponent - Renders a dynamically loaded UI component in Shadow DOM
 *
 * This is the actual renderer component that fetches and displays external components.
 * Use this inside useCopilotAction's render function.
 */
import React, { useRef, useEffect, useState } from 'react';
import type { DynamicUIPayload } from './types';

/**
 * Stream context for HITL (Human-in-the-Loop) interactions.
 * Backend components access this via window.__SIDD_STREAM__
 */
export interface StreamContext {
  /** Send a message to the chat (for retry, user input, etc.) */
  sendMessage?: (message: string) => void;
  /** Resume from an interrupt with a value */
  resume?: (value: unknown) => void;
  /** Current interrupt state (if any) */
  interrupt?: unknown;
}

interface LoadExternalComponentProps {
  payload: DynamicUIPayload;
  apiUrl?: string;
  /** Stream context for HITL - exposed on window.__SIDD_STREAM__ */
  streamContext?: StreamContext;
  onComponentLoad?: (payload: DynamicUIPayload) => void;
  onComponentError?: (error: Error, payload: DynamicUIPayload) => void;
  containerStyle?: React.CSSProperties;
  containerClassName?: string;
}

const DEFAULT_API_URL = "http://localhost:8000";

// Global cache for fetched HTML fragments
// This allows multiple component instances with the same componentId to render without re-fetching
const htmlCache = new Map<string, string>();

// Track in-flight fetches to prevent duplicate requests
const pendingFetches = new Map<string, Promise<string>>();

// Helper to normalize props for comparison (handles different key orders)
function normalizeProps(props: any): any {
  if (!props || typeof props !== 'object') return props;
  return Object.keys(props).sort().reduce((acc, key) => {
    acc[key] = props[key];
    return acc;
  }, {} as any);
}

const LoadExternalComponentInner: React.FC<LoadExternalComponentProps> = ({
  payload,
  apiUrl = DEFAULT_API_URL,
  streamContext,
  onComponentLoad,
  onComponentError,
  containerStyle = {},
  containerClassName = "",
}) => {
  const hostRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const { graph_name, component_name, props } = payload;

  // Expose stream context on window for backend components to access
  useEffect(() => {
    if (streamContext) {
      (window as any).__SIDD_STREAM__ = streamContext;
    }
  }, [streamContext]);

  // Normalize props by sorting keys to handle different key orders
  const normalizedProps = normalizeProps(props);
  const componentId = `${graph_name}:${component_name}:${JSON.stringify(normalizedProps)}`;

  useEffect(() => {
    const hostElement = hostRef.current;
    if (!hostElement) {
      return;
    }

    // Generate a unique ID for this Shadow DOM instance
    const shadowRootId = `sidd-shadow-${Math.random().toString(36).substring(2, 9)}`;

    // Ensure Shadow Root exists on the host element
    const root = hostElement.shadowRoot ?? hostElement.attachShadow({ mode: "open" });

    // Register shadow root in global registry
    (window as any).__SIDD_SHADOW_ROOTS__ = (window as any).__SIDD_SHADOW_ROOTS__ || new Map();
    (window as any).__SIDD_SHADOW_ROOTS__.set(shadowRootId, root);

    // Helper to render HTML into this Shadow DOM
    const renderHtml = (htmlFragment: string) => {
      const finalHtml = htmlFragment.replace(/\{\{shadowRootId\}\}/g, shadowRootId);
      const fragment = document.createRange().createContextualFragment(finalHtml);
      root.innerHTML = '';
      root.appendChild(fragment);
      setLoading(false);
      if (onComponentLoad) onComponentLoad(payload);
    };

    // Check if we already have cached HTML for this component
    const cachedHtml = htmlCache.get(componentId);
    if (cachedHtml) {
      renderHtml(cachedHtml);
      return;
    }

    // Show loading indicator while fetching
    root.innerHTML = `
      <div style="padding: 20px; color: #666; text-align: center; font-family: sans-serif;">
        <div style="font-size: 14px; margin-bottom: 8px;">⚡ Loading ${component_name} component...</div>
        <div style="font-size: 12px; color: #999;">(bundling React + component code)</div>
      </div>
    `;

    // Check if there's already a fetch in progress for this componentId
    let fetchPromise = pendingFetches.get(componentId);

    if (!fetchPromise) {
      // Start new fetch
      const uiEndpointUrl = `${apiUrl}/ui/${graph_name}`;

      fetchPromise = fetch(uiEndpointUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: component_name, props: props })
      })
        .then(res => {
          if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
          return res.text();
        })
        .then(htmlFragment => {
          // Cache the response for other instances
          htmlCache.set(componentId, htmlFragment);
          pendingFetches.delete(componentId);
          return htmlFragment;
        })
        .catch(err => {
          pendingFetches.delete(componentId);
          throw err;
        });

      pendingFetches.set(componentId, fetchPromise);
    }

    // Wait for the fetch (either new or existing)
    fetchPromise
      .then(htmlFragment => {
        renderHtml(htmlFragment);
      })
      .catch(err => {
        console.error(`[Sidd Agent UI] Failed to load component:`, err);
        setError(err.message || 'Unknown error');
        setLoading(false);
        root.innerHTML = `<div style="padding: 10px; color: #dc2626; border: 1px solid #fca5a5; border-radius: 4px; background: #fee2e2;">
          <strong>Error loading UI component:</strong><br/>
          ${err.message || 'Unknown error'}
        </div>`;
        if (onComponentError) onComponentError(err, payload);
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [componentId]);  // Re-run if componentId changes

  // Return the host div element to render in the chat
  return (
    <div
      ref={hostRef}
      className={containerClassName}
      style={{
        minHeight: '100px',
        margin: '10px 0',
        width: '100%',
        ...containerStyle
      }}
    />
  );
};

// Memoize the component to prevent unnecessary re-renders
export const LoadExternalComponent = React.memo(
  LoadExternalComponentInner,
  (prevProps, nextProps) => {
    // Normalize props before comparing
    const prevNormalized = normalizeProps(prevProps.payload.props);
    const nextNormalized = normalizeProps(nextProps.payload.props);

    const prevId = `${prevProps.payload.graph_name}:${prevProps.payload.component_name}:${JSON.stringify(prevNormalized)}`;
    const nextId = `${nextProps.payload.graph_name}:${nextProps.payload.component_name}:${JSON.stringify(nextNormalized)}`;

    return prevId === nextId; // Return true to skip re-render
  }
);

LoadExternalComponent.displayName = 'LoadExternalComponent';

export default LoadExternalComponent;
