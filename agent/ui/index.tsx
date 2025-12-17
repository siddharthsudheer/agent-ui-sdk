const WeatherBackendComponent = (props: { location?: string; temp?: number }) => {
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
    </div>
  );
};

export default {
  weather: WeatherBackendComponent,
};