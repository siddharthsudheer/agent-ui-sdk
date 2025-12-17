/**
 * LoadExternalComponent - Renders a dynamically loaded UI component in Shadow DOM
 *
 * This is the actual renderer component that fetches and displays external components.
 * Use this inside useCopilotAction's render function.
 */
import React, { useRef, useEffect, useState } from 'react';
import type { DynamicUIPayload } from './types';

interface LoadExternalComponentProps {
  payload: DynamicUIPayload;
  apiUrl?: string;
  onComponentLoad?: (payload: DynamicUIPayload) => void;
  onComponentError?: (error: Error, payload: DynamicUIPayload) => void;
  containerStyle?: React.CSSProperties;
  containerClassName?: string;
}

const DEFAULT_API_URL = "http://localhost:8000";

// Global cache to track rendered components across all instances
// This prevents duplicate renders even when CopilotKit re-renders the entire conversation
// or when React Strict Mode unmounts/remounts components
const renderedComponents = new Set<string>();

// Module-level function to atomically register a component
// Returns true if registration succeeded (component should render), false if already registered
function tryRegisterComponent(componentId: string): boolean {
  // Atomic check-and-set to prevent race conditions
  if (renderedComponents.has(componentId)) {
    console.log('[Sidd Agent UI] Component already rendered, skipping:', componentId);
    return false;
  }
  // Mark as rendered IMMEDIATELY (not when fetch completes)
  // This prevents React Strict Mode's unmount+remount from creating duplicates
  renderedComponents.add(componentId);
  console.log('[Sidd Agent UI] Component registered and marked as rendered:', componentId);
  return true;
}

// Helper to normalize props for comparison (handles different key orders)
function normalizeProps(props: any): any {
  if (!props || typeof props !== 'object') return props;

  // Sort keys to ensure {a:1, b:2} and {b:2, a:1} are identical
  return Object.keys(props).sort().reduce((acc, key) => {
    acc[key] = props[key];
    return acc;
  }, {} as any);
}

const LoadExternalComponentInner: React.FC<LoadExternalComponentProps> = ({
  payload,
  apiUrl = DEFAULT_API_URL,
  onComponentLoad,
  onComponentError,
  containerStyle = {},
  containerClassName = "",
}) => {
  const hostRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const { graph_name, component_name, props } = payload;

  // Normalize props by sorting keys to handle different key orders
  const normalizedProps = normalizeProps(props);
  const componentId = `${graph_name}:${component_name}:${JSON.stringify(normalizedProps)}`;

  console.log('[Sidd Agent UI] Props:', props, '→ Normalized:', normalizedProps, '→ ID:', componentId);

  // Register component atomically during render (before useEffect)
  // This prevents race conditions when multiple instances are created simultaneously
  const [shouldRender] = useState(() => tryRegisterComponent(componentId));

  useEffect(() => {
    // If not registered (already exists), skip rendering
    if (!shouldRender) {
      console.log('[Sidd Agent UI] Component not registered, skipping render:', componentId);
      setLoading(false);
      return;
    }

    const hostElement = hostRef.current;
    if (!hostElement) {
      console.error('[Sidd Agent UI] Host ref is null');
      return;
    }

    console.log('[Sidd Agent UI] Starting to load component:', componentId);

    // Generate a unique ID for the Shadow DOM host
    const shadowRootId = `sidd-shadow-${Math.random().toString(36).substring(2, 9)}`;

    // Ensure Shadow Root exists on the host element
    const root = hostElement.shadowRoot ?? hostElement.attachShadow({ mode: "open" });

    // Register shadow root in global registry BEFORE fetching script
    // This ensures the bundle can find it even if the host element is unmounted
    (window as any).__SIDD_SHADOW_ROOTS__ = (window as any).__SIDD_SHADOW_ROOTS__ || new Map();
    (window as any).__SIDD_SHADOW_ROOTS__.set(shadowRootId, root);

    console.log('[Sidd Agent UI] Registered shadow root:', shadowRootId);

    // Clear previous content and show loading indicator
    root.innerHTML = `
      <div style="padding: 20px; color: #666; text-align: center; font-family: sans-serif;">
        <div style="font-size: 14px; margin-bottom: 8px;">⚡ Loading ${component_name} component...</div>
        <div style="font-size: 12px; color: #999;">(bundling React + component code)</div>
      </div>
    `;

    // Construct the URL for the HTML fragment (POST request)
    const uiEndpointUrl = `${apiUrl}/ui/${graph_name}`;

    console.log(`[Sidd Agent UI] Fetching component from: ${uiEndpointUrl}`);

    // Request the HTML fragment from the server
    fetch(uiEndpointUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: component_name, props: props })
    })
      .then(res => {
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        }
        return res.text();
      })
      .then(htmlFragment => {
        console.log(`[Sidd Agent UI] Received HTML fragment for shadowRootId:`, shadowRootId);

        // Replace the placeholder with the actual shadowRootId
        const finalHtml = htmlFragment.replace(/\{\{shadowRootId\}\}/g, shadowRootId);

        console.log(`[Sidd Agent UI] Final HTML:`, finalHtml);

        // Use createContextualFragment to safely parse the HTML and its <script> tag
        const fragment = document
          .createRange()
          .createContextualFragment(finalHtml);

        root.innerHTML = ''; // Clear 'Loading...' message
        root.appendChild(fragment);

        console.log(`[Sidd Agent UI] Injected script into shadow DOM for component: ${component_name}`);

        // Fetch complete
        setLoading(false);

        // Call success callback
        if (onComponentLoad) {
          onComponentLoad(payload);
        }
      })
      .catch(err => {
        console.error(`[Sidd Agent UI] Failed to load component:`, err);
        const errorMsg = err.message || 'Unknown error';
        setError(errorMsg);
        setLoading(false);

        root.innerHTML = `<div style="padding: 10px; color: #dc2626; border: 1px solid #fca5a5; border-radius: 4px; background: #fee2e2;">
          <strong>Error loading UI component:</strong><br/>
          ${errorMsg}
        </div>`;

        // Call error callback
        if (onComponentError) {
          onComponentError(err, payload);
        }
      });

    // Cleanup function
    return () => {
      // Nothing to clean up - component is marked as rendered permanently
      // This ensures React Strict Mode's unmount+remount doesn't create duplicates
    };
  }, [componentId, apiUrl, shouldRender, component_name, graph_name, props, onComponentLoad, onComponentError]);

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
