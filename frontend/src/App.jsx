import "./index.css";

const districts = [
  "Kasaragod",
  "Kannur",
  "Wayanad",
  "Kozhikode",
  "Malappuram",
  "Palakkad",
  "Thrissur",
  "Ernakulam",
  "Idukki",
  "Kottayam",
  "Alappuzha",
  "Pathanamthitta",
  "Kollam",
  "Thiruvananthapuram",
];

function App() {
  return (
    <div className="app">
      {/* TOP NAVBAR */}
      <header className="navbar">
        <div className="brand">
          <h1>KAAVALAL</h1>
          <span>Kerala Disaster Management & Resource Allocation</span>
        </div>

        <div className="system-status">
          <span className="status-dot"></span>
          System Online
        </div>
      </header>

      {/* MAIN APPLICATION */}
      <main className="dashboard">
        {/* LEFT DISTRICT SIDEBAR */}
        <aside className="district-sidebar">
          <div className="sidebar-header">
            <h2>Kerala</h2>
            <span>14 Districts</span>
          </div>

          <div className="district-search">
            <input
              type="text"
              placeholder="Search district..."
            />
          </div>

          <div className="district-list">
            {districts.map((district) => (
              <button
                className="district-item"
                key={district}
              >
                <span className="district-risk-dot"></span>
                <span>{district}</span>
              </button>
            ))}
          </div>
        </aside>

        {/* MAP SECTION */}
        <section className="map-section">
          <div className="map-toolbar">
            <div>
              <span className="map-level">KERALA</span>
              <h2>Disaster Intelligence Map</h2>
            </div>

            <div className="map-controls">
              <button className="active-control">
                Overall Risk
              </button>

              <button>Flood</button>
              <button>Landslide</button>
              <button>Drought</button>
            </div>
          </div>

          <div className="map-container">
            <div className="map-placeholder">
              <div className="map-placeholder-content">
                <div className="map-symbol">KERALA</div>

                <h3>Interactive Kerala Map</h3>

                <p>
                  District boundaries will appear here.
                  Hover over a district to view quick information
                  and click to explore its taluks.
                </p>

                <div className="map-legend">
                  <div>
                    <span className="legend-dot low"></span>
                    Low
                  </div>

                  <div>
                    <span className="legend-dot moderate"></span>
                    Moderate
                  </div>

                  <div>
                    <span className="legend-dot high"></span>
                    High
                  </div>

                  <div>
                    <span className="legend-dot critical"></span>
                    Critical
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* MAP BOTTOM INFORMATION */}
          <div className="map-footer">
            <div>
              <strong>Map Level</strong>
              <span>Districts</span>
            </div>

            <div>
              <strong>Interaction</strong>
              <span>Hover / Click</span>
            </div>

            <div>
              <strong>Next Level</strong>
              <span>Taluks</span>
            </div>
          </div>
        </section>

        {/* RIGHT INFORMATION PANEL */}
        <aside className="information-panel">
          <div className="panel-header">
            <span className="panel-label">SELECTED LOCATION</span>

            <h2>Kerala</h2>

            <p>
              Select a district from the map or district list.
            </p>
          </div>

          {/* WEATHER */}
          <section className="panel-section">
            <div className="section-title">
              <h3>Current Conditions</h3>
            </div>

            <div className="weather-grid">
              <div className="weather-item">
                <span>Temperature</span>
                <strong>-- °C</strong>
              </div>

              <div className="weather-item">
                <span>Humidity</span>
                <strong>-- %</strong>
              </div>

              <div className="weather-item">
                <span>Wind</span>
                <strong>-- km/h</strong>
              </div>

              <div className="weather-item">
                <span>Rainfall 24h</span>
                <strong>-- mm</strong>
              </div>
            </div>
          </section>

          {/* RISK */}
          <section className="panel-section">
            <div className="section-title">
              <h3>Disaster Risk</h3>
            </div>

            <div className="risk-list">
              <div className="risk-row">
                <span>Flood</span>
                <strong className="risk-high">--</strong>
              </div>

              <div className="risk-row">
                <span>Landslide</span>
                <strong className="risk-moderate">--</strong>
              </div>

              <div className="risk-row">
                <span>Drought</span>
                <strong className="risk-low">--</strong>
              </div>
            </div>
          </section>

          {/* EXPOSURE */}
          <section className="panel-section">
            <div className="section-title">
              <h3>Exposure</h3>
            </div>

            <div className="exposure-list">
              <div>
                <span>Population</span>
                <strong>--</strong>
              </div>

              <div>
                <span>Population Density</span>
                <strong>-- / km²</strong>
              </div>

              <div>
                <span>Elevation</span>
                <strong>-- m</strong>
              </div>
            </div>
          </section>

          <button className="explore-button">
            Explore District
          </button>
        </aside>
      </main>

      {/* BOTTOM STATUS BAR */}
      <footer className="footer">
        <span>KAAVALAL</span>
        <span>Kerala Disaster Intelligence Platform</span>
        <span>Data will be connected to FastAPI</span>
      </footer>
    </div>
  );
}

export default App;