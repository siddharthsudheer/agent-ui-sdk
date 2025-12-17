/**
 * Utility for preloading UI bundles to warm the browser cache
 */

/**
 * Preload a UI bundle by injecting a script tag into the document head.
 * This warms the browser cache so when the component is actually rendered,
 * the bundle loads instantly.
 *
 * @param apiUrl - The backend API URL (e.g., "http://localhost:8000")
 * @param graphName - The graph/app name (e.g., "proverbs_app")
 *
 * @example
 * ```tsx
 * import { preloadUIBundle } from '@/sidd_agent_ui_sdk';
 *
 * // In your component or app initialization:
 * useEffect(() => {
 *   preloadUIBundle('http://localhost:8000', 'proverbs_app');
 * }, []);
 * ```
 */
export function preloadUIBundle(apiUrl: string, graphName: string): void {
  if (typeof window === 'undefined') {
    console.warn('[Sidd Agent UI] preloadUIBundle called on server, skipping');
    return;
  }

  const scriptUrl = `${apiUrl}/ui/${graphName}/entrypoint.js`;

  // Check if already loaded
  const existing = document.querySelector(`script[src="${scriptUrl}"]`);
  if (existing) {
    console.log(`[Sidd Agent UI] Bundle already preloaded: ${graphName}`);
    return;
  }

  console.log(`[Sidd Agent UI] Preloading bundle: ${graphName}`);

  const script = document.createElement('script');
  script.src = scriptUrl;
  script.async = true;
  script.onload = () => {
    console.log(`[Sidd Agent UI] ✓ Preloaded bundle: ${graphName}`);
  };
  script.onerror = (error) => {
    console.error(`[Sidd Agent UI] ✗ Failed to preload bundle: ${graphName}`, error);
  };

  document.head.appendChild(script);
}

/**
 * Preload multiple UI bundles at once
 *
 * @param apiUrl - The backend API URL
 * @param graphNames - Array of graph names to preload
 *
 * @example
 * ```tsx
 * preloadUIBundles('http://localhost:8000', ['proverbs_app', 'trading_bot']);
 * ```
 */
export function preloadUIBundles(apiUrl: string, graphNames: string[]): void {
  graphNames.forEach(graphName => preloadUIBundle(apiUrl, graphName));
}
