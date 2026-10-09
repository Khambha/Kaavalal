  
import { useEffect, useState } from "react";
import axios from "axios";
import "./index.css";

const API_URL = "http://127.0.0.1:8000";

const districts = [
  { id: 14, name: "Kasaragod" },
  { id: 13, name: "Kannur" },
  { id: 12, name: "Wayanad" },
  { id: 11, name: "Kozhikode" },
  { id: 10, name: "Malappuram" },
  { id: 9, name: "Palakkad" },
  { id: 8, name: "Thrissur" },
  { id: 7, name: "Ernakulam" },
  { id: 6, name: "Idukki" },
  { id: 5, name: "Kottayam" },
  { id: 4, name: "Alappuzha" },
  { id: 3, name: "Pathanamthitta" },
  { id: 2, name: "Kollam" },
  { id: 1, name: "Thiruvananthapuram" },
];

function formatValue(value, suffix = "") {
  if (value === null || value === undefined || value === "") {
    return "--";
  }

  return `${value}${suffix}`;
}

function riskClass(value) {
  if (value === null || value === undefined) {
    return "";
  }

  if (value >= 75) return "risk-high";
  if (value >= 40) return "risk-moderate";
  return "risk-low";
}

function App() {
  const [selectedDistrict, setSelectedDistrict] = useState(districts[7]);
  const [dashboard, setDashboard] = useState(null);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [apiOnline, setApiOnline] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadDashboard() {
      setLoading(true);
      setError("");
      setDashboard(null);

      try {
        const response = await axios.get(
          `${API_URL}/api/dashboard/${selectedDistrict.id}`
        );

        if (!cancelled) {
          setDashboard(response.data);
          setApiOnline(true);
        }
      } catch (err) {
        if (!cancelled) {
          setApiOnline(false);

          if (err.response?.status === 404) {
            setError("This district or its dashboard data could not be found.");
          } else {
            setError(
              "Could not connect to the backend. Make sure FastAPI is running."
            );
          }
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadDashboard();

    return () => {
      cancelled = true;
    };
  }, [selectedDistrict]);

  const filteredDistricts = districts.filter((district) =>
    district.name.toLowerCase().includes(search.toLowerCase())
  );

  const location = dashboard?.location;
  const weather = dashboard?.weather;
  const rainfall = dashboard?.rainfall;
  const hazards = dashboard?.hazards;
  const risk = dashboard?.risk;

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
          {loading
            ? "Loading..."
            : apiOnline
              ? "API Connected"
              : "API Disconnected"}
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
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>

          <div className="district-list">
            {filteredDistricts.map((district) => (
              <button
                className={`district-item ${
                  selectedDistrict.id === district.id ? "selected" : ""
                }`}
                key={district.id}
                onClick={() => setSelectedDistrict(district)}
              >
                <span className="district-risk-dot"></span>
                <span>{district.name}</span>
              </button>
            ))}

            {filteredDistricts.length === 0 && (
              <p>No districts found.</p>
            )}
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
              <button className="active-control">Overall Risk</button>
              <button>Flood</button>
              <button>Landslide</button>
              <button>Drought</button>
            </div>
          </div>

          <div className="map-container">
            <div className="map-placeholder">
              <div className="map-placeholder-content">
                <div className="map-symbol">KERALA</div>

                <h3>{selectedDistrict.name}</h3>

                <p>
                  {location?.latitude != null &&
                  location?.longitude != null
                    ? `Coordinates: ${location.latitude}, ${location.longitude}`
                    : "District boundaries will appear here."}
                </p>

                <p>
                  The interactive map will be added as part of the GIS module.
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
              <strong>Selected District</strong>
              <span>{selectedDistrict.name}</span>
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

            <h2>{location?.name || selectedDistrict.name}</h2>

            <p>
              {location?.location_type || "District"}
              {location?.coastal_status
                ? ` • ${location.coastal_status}`
                : ""}
            </p>
          </div>

          {loading && (
            <p className="panel-section">Loading district information...</p>
          )}

          {error && (
            <div className="panel-section">
              <p role="alert">{error}</p>
              <button
                onClick={() =>
                  setSelectedDistrict({ ...selectedDistrict })
                }
              >
                Retry
              </button>
            </div>
          )}

          {/* WEATHER */}
          <section className="panel-section">
            <div className="section-title">
              <h3>Current Conditions</h3>
            </div>

            <div className="weather-grid">
              <div className="weather-item">
                <span>Temperature</span>
                <strong>{formatValue(weather?.temperature, " °C")}</strong>
              </div>

              <div className="weather-item">
                <span>Humidity</span>
                <strong>{formatValue(weather?.humidity, " %")}</strong>
              </div>

              <div className="weather-item">
                <span>Wind</span>
                <strong>{formatValue(weather?.wind_speed, " km/h")}</strong>
              </div>

              <div className="weather-item">
                <span>Rainfall 24h</span>
                <strong>{formatValue(rainfall?.rainfall_24h, " mm")}</strong>
              </div>
            </div>

            {!weather && !loading && !error && (
              <p>Weather data is currently unavailable.</p>
            )}
          </section>

          {/* RISK */}
          <section className="panel-section">
            <div className="section-title">
              <h3>Disaster Risk</h3>
            </div>

            <div className="risk-list">
              <div className="risk-row">
                <span>Flood</span>
                <strong className={riskClass(risk?.flood_risk)}>
                  {formatValue(risk?.flood_risk, "%")}
                </strong>
              </div>

              <div className="risk-row">
                <span>Landslide</span>
                <strong className={riskClass(risk?.landslide_risk)}>
                  {formatValue(risk?.landslide_risk, "%")}
                </strong>
              </div>

              <div className="risk-row">
                <span>Drought</span>
                <strong className={riskClass(risk?.drought_risk)}>
                  {formatValue(risk?.drought_risk, "%")}
                </strong>
              </div>

              <div className="risk-row">
                <span>Overall Risk</span>
                <strong className={riskClass(risk?.overall_risk)}>
                  {formatValue(risk?.overall_risk, "%")}
                </strong>
              </div>
            </div>

            {!risk && !loading && !error && (
              <p>Risk data is currently unavailable.</p>
            )}
          </section>

          {/* HAZARDS */}
          <section className="panel-section">
            <div className="section-title">
              <h3>Hazard Levels</h3>
            </div>

            <div className="risk-list">
              <div className="risk-row">
                <span>Flood</span>
                <strong>{hazards?.flood_level ?? "--"}</strong>
              </div>

              <div className="risk-row">
                <span>Landslide</span>
                <strong>{hazards?.landslide_level ?? "--"}</strong>
              </div>

              <div className="risk-row">
                <span>Drought</span>
                <strong>{hazards?.drought_level ?? "--"}</strong>
              </div>

              <div className="risk-row">
                <span>Earthquake</span>
                <strong>{hazards?.earthquake_level ?? "--"}</strong>
              </div>

              <div className="risk-row">
                <span>Coastal</span>
                <strong>{hazards?.coastal_level ?? "--"}</strong>
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
                <strong>
                  {location?.population != null
                    ? location.population.toLocaleString("en-IN")
                    : "--"}
                </strong>
              </div>

              <div>
                <span>Population Density</span>
                <strong>
                  {formatValue(location?.population_density, " / km²")}
                </strong>
              </div>

              <div>
                <span>Elevation</span>
                <strong>{formatValue(location?.elevation_m, " m")}</strong>
              </div>

              <div>
                <span>Area</span>
                <strong>{formatValue(location?.area_sq_km, " km²")}</strong>
              </div>
            </div>
          </section>

          <button
            className="explore-button"
            onClick={() =>
              setSelectedDistrict({ ...selectedDistrict })
            }
          >
            Refresh District Data
          </button>
        </aside>
      </main>

      {/* BOTTOM STATUS BAR */}
      <footer className="footer">
        <span>KAAVALAL</span>
        <span>Kerala Disaster Intelligence Platform</span>
        <span>
          {apiOnline ? "Connected to FastAPI" : "Waiting for API connection"}
        </span>
      </footer>
    </div>
  );
}

export default App;

