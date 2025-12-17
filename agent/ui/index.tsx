// Type for the stream context exposed by the frontend
interface SiddStream {
  sendMessage?: (message: string) => void;
  resume?: (value: unknown) => void;
  interrupt?: unknown;
}

// Access the stream context from window
const getStream = (): SiddStream | undefined => {
  return (window as any).__SIDD_STREAM__;
};

const WeatherBackendComponent = (props: { location?: string; temp?: number }) => {
  const handleRetry = () => {
    const stream = getStream();
    if (stream?.sendMessage) {
      stream.sendMessage(`What's the weather in ${props.location || 'my location'}?`);
    } else {
      console.warn('[WeatherComponent] Stream context not available');
    }
  };

  return (
    <div style={{
      padding: '20px',
      backgroundColor: '#2b7fff',
      color: 'white',
      borderRadius: '8px',
      fontFamily: 'sans-serif'
    }}>
      <h3 style={{ margin: '0 0 10px 0' }}>Weather (Backend Component)</h3>
      {props.location && <p style={{ margin: '5px 0' }}>Location: {props.location}</p>}
      {props.temp && <p style={{ margin: '5px 0' }}>Temperature: {props.temp}°F</p>}
      {!props.location && !props.temp && <p>No weather data available</p>}
      <button
        onClick={handleRetry}
        style={{
          marginTop: '10px',
          padding: '8px 16px',
          backgroundColor: 'white',
          color: '#2b7fff',
          border: 'none',
          borderRadius: '4px',
          cursor: 'pointer',
          fontWeight: 'bold'
        }}
      >
        Retry
      </button>
    </div>
  );
};

export default {
  weather: WeatherBackendComponent,
};
