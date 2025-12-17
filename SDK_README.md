# Sidd Agent UI SDK

A framework-agnostic SDK for building dynamic UI components in AI agent applications, inspired by LangGraph's generative UI pattern.

## Architecture

This SDK consists of two packages:
- **Backend SDK** (`agent/sidd_agent_ui_sdk/`) - Python package for bundling and serving UI components
- **Frontend SDK** (`src/sidd_agent_ui_sdk/`) - React package for loading and rendering dynamic components

## Features

- 🎯 **Framework Agnostic** - Works with any Python backend (FastAPI, Flask, Django) and React frontend
- 🔒 **Shadow DOM Isolation** - Components render in isolated Shadow DOM for style encapsulation
- 📦 **Automatic Bundling** - Uses esbuild to bundle React components on-demand
- 🚀 **Lazy Loading** - Components are only loaded when needed
- 🔄 **Two-Stage Loading** - Efficient HTML + JS bundle pattern
- 💾 **Caching** - Built-in caching for bundled components

---

## Backend SDK

### Installation

```bash
cd agent
pip install -r requirements.txt
```

**Note:** Requires `esbuild` to be installed globally or via npm:
```bash
npm install -g esbuild
# or
npm install esbuild
```

### Quick Start

1. **Create your UI components** (`agent/ui/index.tsx`):

```tsx
const WeatherComponent = (props: { location: string; temp: number }) => {
  return (
    <div style={{ padding: '20px', backgroundColor: '#3b82f6', color: 'white' }}>
      <h3>Weather in {props.location}</h3>
      <p>Temperature: {props.temp}°F</p>
    </div>
  );
};

export default {
  weather: WeatherComponent,
};
```

2. **Setup the backend** (`agent/agent.py`):

```python
from sidd_agent_ui_sdk import UIManager

# One-line setup! 🎉
ui = UIManager(graph_name="my_app", ui_path="./ui/index.tsx")

# Use with your agent and app
agent = LlmAgent(
    name="MyAgent",
    tools=[my_tool, ui.tool],  # ← Add ui.tool to your agent
    instruction="""
    When showing weather, call push_ui_message with:
    - component_name: "weather"
    - props: {"location": "City", "temp": 72}
    """
)

# FastAPI setup (⚡ auto-bundles on startup!)
app = FastAPI(lifespan=ui.lifespan)  # ← Handles preloading
app.include_router(ui.router)        # ← Adds /ui/* endpoints
```

That's it for the backend! The `UIManager` handles:
- ✅ Creating the `push_ui_message` tool
- ✅ Setting up FastAPI routes
- ✅ Pre-bundling components on startup
- ✅ Caching for instant renders

### API Reference

#### `UIManager` (Recommended)

Simplified manager with everything you need:

```python
from sidd_agent_ui_sdk import UIManager

ui = UIManager(
    graph_name="my_app",
    ui_path="./ui/index.tsx",
    preload=True  # Optional: disable startup bundling (default: True)
)
```

**Properties:**
- `ui.tool` - The push_ui_message tool for your LLM agent
- `ui.router` - FastAPI router with /ui/* endpoints
- `ui.lifespan` - Lifespan context manager for FastAPI (handles preloading)

**Methods:**
- `await ui.preload_bundle()` - Manually pre-bundle (if not using lifespan)
- `ui.invalidate_cache()` - Force re-bundling (useful during development)

**Example:**
```python
ui = UIManager(graph_name="my_app", ui_path="./ui/index.tsx")
agent = LlmAgent(tools=[ui.tool])
app = FastAPI(lifespan=ui.lifespan)
app.include_router(ui.router)
```

#### `UIServer` (Advanced)

Lower-level API for custom setups. See `UIManager` source for usage.

#### Endpoints

The UI server automatically creates these endpoints:

- `POST /ui/{graph_name}` - Get HTML fragment with script tag
- `GET /ui/{graph_name}/entrypoint.js` - Get bundled JavaScript
- `POST /ui/{graph_name}/entrypoint.js` - Get bundled JavaScript (POST)
- `GET /ui/{graph_name}/invalidate` - Invalidate component cache

---

## Frontend SDK

### Installation

```bash
npm install
# or
pnpm install
```

### Quick Start

**Setup (one-time, in your app):**

```tsx
import { LoadExternalComponent, preloadUIBundle } from '@/sidd_agent_ui_sdk';
import { useCopilotAction } from '@copilotkit/react-core';
import { useEffect } from 'react';

function MyApp() {
  // Optional: Preload bundle on mount for instant first render
  useEffect(() => {
    preloadUIBundle('http://localhost:8000', 'my_app');
  }, []);

  // Wire up to your framework (CopilotKit example)
  useCopilotAction({
    name: "push_ui_message",
    available: "disabled",
    parameters: [
      { name: "component_name", type: "string", required: true },
      { name: "props", type: "object", required: true },
    ],
    render: ({ args }) => {
      const payload = {
        graph_name: "my_app",
        component_name: args.component_name,
        props: args.props || {}
      };
      return <LoadExternalComponent payload={payload} apiUrl="http://localhost:8000" />;
    },
  });

  return <div>Your app content</div>;
}
```

That's it! The SDK is framework-agnostic - you wire it up to your framework of choice.

### API Reference

#### `LoadExternalComponent`

Renders a dynamically loaded UI component in Shadow DOM.

```tsx
interface LoadExternalComponentProps {
  payload: DynamicUIPayload;  // Required: {graph_name, component_name, props}
  apiUrl?: string;
  onComponentLoad?: (payload: DynamicUIPayload) => void;
  onComponentError?: (error: Error, payload: DynamicUIPayload) => void;
  containerStyle?: React.CSSProperties;
  containerClassName?: string;
}
```

**Props:**
- `payload` - **Required**: Contains graph_name, component_name, and props
- `apiUrl` - Backend server URL (default: "http://localhost:8000")
- `onComponentLoad` - Callback when component loads successfully
- `onComponentError` - Callback when component loading fails
- `containerStyle` - Custom styles for host container
- `containerClassName` - Custom class name for host container

#### `preloadUIBundle(apiUrl, graphName)`

Preloads a UI bundle by injecting a script tag. This warms the browser cache so the first render is instant.

```tsx
preloadUIBundle('http://localhost:8000', 'my_app');
```

**Why preload?**
- Backend bundles on startup (server cache warm)
- Frontend preloads on mount (browser cache warm)
- Result: **Instant first render** ⚡

#### `preloadUIBundles(apiUrl, graphNames[])`

Preload multiple bundles at once:

```tsx
preloadUIBundles('http://localhost:8000', ['my_app', 'another_app']);
```

### CopilotKit Integration

This SDK is designed to work seamlessly with CopilotKit:

```tsx
import { CopilotKit } from "@copilotkit/react-core";
import { LoadExternalComponent } from '@/sidd_agent_ui_sdk';

function App() {
  return (
    <CopilotKit runtimeUrl="/api/copilotkit" agent="my_agent">
      <LoadExternalComponent apiUrl="http://localhost:8000" />
      {/* Your app content */}
    </CopilotKit>
  );
}
```

---

## How It Works

### The Flow

1. **Backend startup**: Components are pre-bundled (takes 2-3s, happens once)

2. **LLM calls tool**: Agent decides to show UI and calls `push_ui_message("weather", {"location": "SF", "temp": 72})`

3. **Frontend intercepts**: `LoadExternalComponent` catches the tool call

4. **Two-stage fetch** (instant, from cache):
   - POST to `/ui/proverbs_app` → Returns HTML with `<script>` tag
   - Browser fetches `/ui/proverbs_app/entrypoint.js` → Returns **cached** bundle

5. **Shadow DOM render**: Script executes, creates Shadow DOM, renders React component

### Performance: Preloading on Startup

**Why pre-bundle on startup?**

The bundle contains **static component code**, not dynamic data:
```tsx
// Static (bundled once):
const WeatherComponent = (props) => <div>{props.location}: {props.temp}°F</div>

// Dynamic (changes at runtime):
push_ui_message("weather", {location: "Atlanta", temp: 72})
push_ui_message("weather", {location: "SF", temp: 65})
```

**Performance comparison:**

| Scenario | First Render | Subsequent Renders |
|----------|--------------|-------------------|
| **Without preload** | 2-3 seconds | Instant (cached) |
| **With preload** | **Instant** | Instant (cached) |

Trade-off: Backend startup takes 2-3s longer, but users never wait!

### Why Shadow DOM?

- **Style Isolation** - Component styles don't leak to parent app
- **Framework Agnostic** - Backend can work with any frontend (not just React)
- **Lightweight** - Main app bundle stays small
- **Security** - Components run in isolated DOM context

---

## Development Workflow

### Running the Development Server

```bash
# Using Makefile (recommended)
make dev

# Or manually
npm run dev:ui    # Start Next.js (port 3000)
npm run dev:agent # Start agent (port 8000)
```

### Testing UI Components

1. Ask the agent: "What's the weather in San Francisco?"
2. Agent will call `push_ui_message` with weather data
3. Frontend will render the weather component in Shadow DOM

### Cache Management

During development, you can invalidate the bundle cache:

```bash
curl http://localhost:8000/ui/proverbs_app/invalidate
```

Or set environment variable:
```bash
export SIDD_UI_ENV=dev  # Enables inline sourcemaps
```

---

## Configuration

### Environment Variables

**Backend:**
- `SIDD_UI_ENV` - Environment mode (`dev` or `production`)
- `SIDD_UI_TARGET` - esbuild target (default: `es2020`)

**UIServer options:**
```python
ui_server = UIServer(
    graph_name="my_app",
    ui_path="./ui/index.tsx",
    preload=True  # Set to False to disable startup bundling (default: True)
)
```

**Frontend:**
- Configure via `LoadExternalComponent` props

---

## Extracting as Packages

These SDKs are organized to be easily extracted into standalone packages:

### Backend Package

```bash
cd agent/sidd_agent_ui_sdk
# Add setup.py and publish to PyPI
```

### Frontend Package

```bash
cd src/sidd_agent_ui_sdk
# Add package.json and publish to npm
```

---

## Troubleshooting

### "esbuild not found"

Install esbuild:
```bash
npm install -g esbuild
```

Or add to your project:
```bash
npm install esbuild
```

### "Component not found"

Make sure your component is exported in the default export:
```tsx
export default {
  componentName: YourComponent,
};
```

### "Shadow root not found"

Check browser console for detailed logs prefixed with `[Sidd Agent UI]`.

### UI not updating

1. Check that `LoadExternalComponent` is rendered
2. Verify agent is calling `push_ui_message`
3. Check Network tab for `/ui/` requests
4. Invalidate cache: `GET /ui/{graph_name}/invalidate`

---

## Examples

See `agent/agent.py` and `src/app/page.tsx` for complete working examples.

## License

MIT
