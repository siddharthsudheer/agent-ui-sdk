"use client";

import { useCopilotAction } from "@copilotkit/react-core";
import { CopilotSidebar } from "@copilotkit/react-ui";
import { useEffect, useState } from "react";
import { LoadExternalComponent, preloadUIBundle, useUIStream } from "@/sidd_agent_ui_sdk";

export default function WeatherPage() {
  // Use a consistent session ID for both streaming and CopilotKit
  // TODO Phase 2: Get from auth/cookie for multi-user support
  const [sessionId] = useState(() => 'demo-session');

  // Streaming components (Phase 2: full return signature!)
  const { components, connected, error } = useUIStream('http://localhost:8000', sessionId);

  useEffect(() => {
    preloadUIBundle('http://localhost:8000', 'weather_app');
  }, []);

  useCopilotAction({
    name: "push_ui_message",
    available: "disabled",
    parameters: [
      { name: "component_name", type: "string", required: true },
      { name: "props", type: "object", required: true },
    ],
    render: ({ args }) => {
      const payload = {
        graph_name: "weather_app",
        component_name: args.component_name,
        props: args.props || {}
      };
      return (
        <div
          className="animate-fade-in"
          style={{
            animation: 'fadeIn 0.3s ease-in',
            animationFillMode: 'both',
          }}
        >
          <LoadExternalComponent payload={payload} apiUrl="http://localhost:8000" />
        </div>
      );
    },
  });

  return (
    <main className="h-screen w-screen bg-blue-500 flex items-center justify-center relative">
      {/* Main content area */}
      <div className="bg-white/20 backdrop-blur-md p-8 rounded-2xl shadow-xl max-w-2xl w-full max-h-[80vh] overflow-y-auto">
        <h1 className="text-4xl font-bold text-white mb-2 text-center">Weather Assistant</h1>
        <p className="text-gray-200 text-center mb-6">Ask me about the weather!</p>

        {/* Live Updates Panel - Streaming Components */}
        {components.length > 0 && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-white/90 text-sm font-medium">
              <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
              Live Updates
              {!connected && <span className="text-yellow-300 text-xs">(Reconnecting...)</span>}
            </div>
            <div className="space-y-3">
              {components.map((component) => (
                <div
                  key={component.id}
                  className="animate-fade-in"
                  style={{
                    animation: 'fadeIn 0.3s ease-in',
                    animationFillMode: 'both',
                  }}
                >
                  <LoadExternalComponent
                    payload={component}
                    apiUrl="http://localhost:8000"
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Empty state when no components */}
        {components.length === 0 && (
          <div className="text-center text-white/60 text-sm py-8">
            {connected ? (
              <>💬 Ask me about the weather to see live updates!</>
            ) : (
              <>⚡ Connecting to streaming...</>
            )}
          </div>
        )}
      </div>

      {/* Error display */}
      {error && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 bg-red-500 text-white px-6 py-3 rounded-lg shadow-lg z-20 animate-fade-in">
          ⚠️ {error}
        </div>
      )}

      {/* Chat sidebar - shows conversation history with tool-based components */}
      <CopilotSidebar
        defaultOpen={true}
        labels={{
          title: "Weather Assistant",
          initial: "Ask me about the weather in any city!"
        }}
      />

      <style jsx>{`
        @keyframes fadeIn {
          from {
            opacity: 0;
            transform: translateY(10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
      `}</style>
    </main>
  );
}
