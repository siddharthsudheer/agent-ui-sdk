/**
 * Sidd Agent UI SDK - Frontend
 *
 * Generic React SDK for loading and rendering dynamic UI components
 * from agent backends. Works with any React application.
 *
 * @example
 * ```tsx
 * import { LoadExternalComponent, preloadUIBundle } from '@/sidd_agent_ui_sdk';
 * import { useCopilotAction } from '@copilotkit/react-core';
 * import { useEffect } from 'react';
 *
 * function MyComponent() {
 *   // Optional: Preload bundle on mount for instant first render
 *   useEffect(() => {
 *     preloadUIBundle('http://localhost:8000', 'proverbs_app');
 *   }, []);
 *
 *   // Wire up to your framework
 *   useCopilotAction({
 *     name: "push_ui_message",
 *     render: ({ args }) => {
 *       const payload = {
 *         graph_name: "proverbs_app",
 *         component_name: args.component_name,
 *         props: args.props || {}
 *       };
 *       return <LoadExternalComponent payload={payload} apiUrl="http://localhost:8000" />;
 *     },
 *   });
 *
 *   return <div>Your app content</div>;
 * }
 * ```
 */

export { LoadExternalComponent } from './LoadExternalComponent';
export { preloadUIBundle, preloadUIBundles } from './preload';
export { useUIStream } from './useUIStream';
export type { DynamicUIPayload } from './types';

export const version = "0.1.0";
