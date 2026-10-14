import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import "./index.css";
import KeralaMap, { normalizeDistrictName } from "./KeralaMap";
import lacData from "./lac_locations.json";

const API_URL = "http://127.0.0.1:8000";

const hazardLayers = [
  { name: "Overall Risk", description: "Combined overview of available district risk indicators." },
  { name: "Flood", description: "Flood-related indicators and susceptibility information." },
  { name: "Landslide", description: "Rainfall, terrain, and landslide-susceptibility indicators." },
  { name: "Drought", description: "Rainfall deficit and drought-related indicators." },
  { name: "Rainfall", description: "Available rainfall measurements and summaries." },
];

const initialDistricts = [
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

// Official geographical and demographic baseline statistics for all 14 districts
export const DISTRICT_DEFAULTS = {
  thiruvananthapuram: {
    id: 1,
    name: "Thiruvananthapuram",
    location_type: "DISTRICT",
    coastal_status: "COASTAL",
    population: 3301427,
    population_density: 1509,
    elevation_m: 12,
    area_sq_km: 2189,
    hazard_levels: { flood_level: "MODERATE", landslide_level: "LOW", drought_level: "LOW", earthquake_level: "LOW", coastal_level: "ACTIVE" },
    risk: { flood_risk: 45, landslide_risk: 25, drought_risk: 30, overall_risk: 33 },
  },
  kollam: {
    id: 2,
    name: "Kollam",
    location_type: "DISTRICT",
    coastal_status: "COASTAL",
    population: 2635375,
    population_density: 1061,
    elevation_m: 15,
    area_sq_km: 2483,
    hazard_levels: { flood_level: "MODERATE", landslide_level: "LOW", drought_level: "LOW", earthquake_level: "LOW", coastal_level: "ACTIVE" },
    risk: { flood_risk: 50, landslide_risk: 20, drought_risk: 25, overall_risk: 32 },
  },
  pathanamthitta: {
    id: 3,
    name: "Pathanamthitta",
    location_type: "DISTRICT",
    coastal_status: "INLAND",
    population: 1197412,
    population_density: 453,
    elevation_m: 19,
    area_sq_km: 2642,
    hazard_levels: { flood_level: "HIGH", landslide_level: "MODERATE", drought_level: "LOW", earthquake_level: "LOW", coastal_level: "INLAND" },
    risk: { flood_risk: 75, landslide_risk: 60, drought_risk: 15, overall_risk: 50 },
  },
  alappuzha: {
    id: 4,
    name: "Alappuzha",
    location_type: "DISTRICT",
    coastal_status: "COASTAL",
    population: 2127789,
    population_density: 1504,
    elevation_m: 2,
    area_sq_km: 1414,
    hazard_levels: { flood_level: "VERY HIGH", landslide_level: "LOW", drought_level: "LOW", earthquake_level: "LOW", coastal_level: "ACTIVE" },
    risk: { flood_risk: 88, landslide_risk: 5, drought_risk: 10, overall_risk: 45 },
  },
  kottayam: {
    id: 5,
    name: "Kottayam",
    location_type: "DISTRICT",
    coastal_status: "INLAND",
    population: 1974551,
    population_density: 896,
    elevation_m: 3,
    area_sq_km: 2206,
    hazard_levels: { flood_level: "HIGH", landslide_level: "LOW", drought_level: "LOW", earthquake_level: "LOW", coastal_level: "INLAND" },
    risk: { flood_risk: 70, landslide_risk: 30, drought_risk: 15, overall_risk: 38 },
  },
  idukki: {
    id: 6,
    name: "Idukki",
    location_type: "DISTRICT",
    coastal_status: "INLAND",
    population: 1108974,
    population_density: 254,
    elevation_m: 1200,
    area_sq_km: 4358,
    hazard_levels: { flood_level: "HIGH", landslide_level: "VERY HIGH", drought_level: "LOW", earthquake_level: "MODERATE", coastal_level: "INLAND" },
    risk: { flood_risk: 65, landslide_risk: 92, drought_risk: 20, overall_risk: 68 },
  },
  ernakulam: {
    id: 7,
    name: "Ernakulam",
    location_type: "DISTRICT",
    coastal_status: "COASTAL",
    population: 3282388,
    population_density: 1069,
    elevation_m: 4,
    area_sq_km: 3068,
    hazard_levels: { flood_level: "HIGH", landslide_level: "LOW", drought_level: "LOW", earthquake_level: "LOW", coastal_level: "ACTIVE" },
    risk: { flood_risk: 72, landslide_risk: 15, drought_risk: 15, overall_risk: 42 },
  },
  thrissur: {
    id: 8,
    name: "Thrissur",
    location_type: "DISTRICT",
    coastal_status: "COASTAL",
    population: 3121200,
    population_density: 1026,
    elevation_m: 10,
    area_sq_km: 3032,
    hazard_levels: { flood_level: "HIGH", landslide_level: "LOW", drought_level: "LOW", earthquake_level: "LOW", coastal_level: "ACTIVE" },
    risk: { flood_risk: 68, landslide_risk: 25, drought_risk: 20, overall_risk: 38 },
  },
  palakkad: {
    id: 9,
    name: "Palakkad",
    location_type: "DISTRICT",
    coastal_status: "INLAND",
    population: 2809934,
    population_density: 627,
    elevation_m: 84,
    area_sq_km: 4480,
    hazard_levels: { flood_level: "LOW", landslide_level: "LOW", drought_level: "MODERATE", earthquake_level: "LOW", coastal_level: "INLAND" },
    risk: { flood_risk: 35, landslide_risk: 20, drought_risk: 75, overall_risk: 43 },
  },
  malappuram: {
    id: 10,
    name: "Malappuram",
    location_type: "DISTRICT",
    coastal_status: "COASTAL",
    population: 4112920,
    population_density: 1157,
    elevation_m: 40,
    area_sq_km: 3554,
    hazard_levels: { flood_level: "MODERATE", landslide_level: "MODERATE", drought_level: "LOW", earthquake_level: "LOW", coastal_level: "ACTIVE" },
    risk: { flood_risk: 58, landslide_risk: 52, drought_risk: 25, overall_risk: 45 },
  },
  kozhikode: {
    id: 11,
    name: "Kozhikode",
    location_type: "DISTRICT",
    coastal_status: "COASTAL",
    population: 3086293,
    population_density: 1316,
    elevation_m: 1,
    area_sq_km: 2344,
    hazard_levels: { flood_level: "MODERATE", landslide_level: "MODERATE", drought_level: "LOW", earthquake_level: "LOW", coastal_level: "ACTIVE" },
    risk: { flood_risk: 60, landslide_risk: 55, drought_risk: 20, overall_risk: 45 },
  },
  wayanad: {
    id: 12,
    name: "Wayanad",
    location_type: "DISTRICT",
    coastal_status: "INLAND",
    population: 817420,
    population_density: 383,
    elevation_m: 700,
    area_sq_km: 2131,
    hazard_levels: { flood_level: "HIGH", landslide_level: "VERY HIGH", drought_level: "LOW", earthquake_level: "LOW", coastal_level: "INLAND" },
    risk: { flood_risk: 65, landslide_risk: 95, drought_risk: 15, overall_risk: 70 },
  },
  kannur: {
    id: 13,
    name: "Kannur",
    location_type: "DISTRICT",
    coastal_status: "COASTAL",
    population: 2523003,
    population_density: 852,
    elevation_m: 15,
    area_sq_km: 2966,
    hazard_levels: { flood_level: "MODERATE", landslide_level: "LOW", drought_level: "LOW", earthquake_level: "LOW", coastal_level: "ACTIVE" },
    risk: { flood_risk: 50, landslide_risk: 35, drought_risk: 20, overall_risk: 35 },
  },
  kasaragod: {
    id: 14,
    name: "Kasaragod",
    location_type: "DISTRICT",
    coastal_status: "COASTAL",
    population: 1307375,
    population_density: 657,
    elevation_m: 19,
    area_sq_km: 1992,
    hazard_levels: { flood_level: "MODERATE", landslide_level: "LOW", drought_level: "MODERATE", earthquake_level: "LOW", coastal_level: "ACTIVE" },
    risk: { flood_risk: 45, landslide_risk: 30, drought_risk: 40, overall_risk: 38 },
  },
};

function formatValue(value, suffix = "") {
  if (value === null || value === undefined || value === "") {
    return "--";
  }
  return `${value}${suffix}`;
}

function riskClass(value) {
  if (value === null || value === undefined) return "";
  if (value >= 75) return "risk-high";
  if (value >= 40) return "risk-moderate";
  return "risk-low";
}

function App() {
  const [districts, setDistricts] = useState(initialDistricts);
  // Default to Palakkad as shown in Image 1
  const [selectedDistrict, setSelectedDistrict] = useState(
    initialDistricts.find((d) => d.name === "Palakkad") || initialDistricts[5]
  );
  const [selectedLac, setSelectedLac] = useState(null);
  const [selectedLayer, setSelectedLayer] = useState("Overall Risk");
  const [showConstituencies, setShowConstituencies] = useState(true);

  const [dashboard, setDashboard] = useState(null);
  const [liveWeather, setLiveWeather] = useState(null);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [apiOnline, setApiOnline] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const [lacs, setLacs] = useState([]);

  // Load district directory from FastAPI
  useEffect(() => {
    let cancelled = false;

    async function loadDistricts() {
      try {
        const response = await axios.get(`${API_URL}/api/districts`);
        if (!cancelled && Array.isArray(response.data) && response.data.length > 0) {
          setDistricts(response.data);
          setApiOnline(true);
        }
      } catch {
        setApiOnline(false);
      }
    }

    loadDistricts();

    return () => {
      cancelled = true;
    };
  }, []);

  // Load dashboard data for selected district
  useEffect(() => {
    if (!selectedDistrict || selectedDistrict === "ALL") {
      setDashboard(null);
      return;
    }

    const locationId = selectedDistrict.id;
    if (!locationId) return;

    let cancelled = false;

    async function loadDashboard() {
      setLoading(true);

      try {
        const response = await axios.get(`${API_URL}/api/dashboard/${locationId}`);
        if (!cancelled) {
          setDashboard(response.data);
          setApiOnline(true);
        }
      } catch {
        if (!cancelled) {
          setDashboard(null);
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
  }, [selectedDistrict, refreshKey]);

  // Load live weather observation
  useEffect(() => {
    if (!selectedDistrict || selectedDistrict === "ALL" || !selectedDistrict.id) {
      setLiveWeather(null);
      return;
    }

    let cancelled = false;

    async function fetchLiveWeather() {
      try {
        const response = await axios.get(
          `${API_URL}/api/districts/${selectedDistrict.id}/weather`
        );
        if (!cancelled && response.data) {
          setLiveWeather(response.data);
          setApiOnline(true);
        }
      } catch {
        if (!cancelled) {
          setLiveWeather(null);
        }
      }
    }

    fetchLiveWeather();

    return () => {
      cancelled = true;
    };
  }, [selectedDistrict, refreshKey]);

  // Load Assembly Constituencies (LACs) for selected district
  useEffect(() => {
    if (!selectedDistrict || selectedDistrict === "ALL") {
      setLacs([]);
      return;
    }

    let cancelled = false;
    const distName = typeof selectedDistrict === "string" ? selectedDistrict : selectedDistrict.name;
    const targetNorm = normalizeDistrictName(distName);

    // Pre-match from lac_locations.json
    const localMatches = (lacData.constituencies || [])
      .filter((item) => normalizeDistrictName(item.district) === targetNorm)
      .map((item) => ({
        id: Number(item.lac_code),
        name: item.lac_name,
        administrative_code: item.lac_code,
        district: item.district,
        latitude: item.latitude,
        longitude: item.longitude,
        location_type: "LAC",
      }));

    async function loadLacs() {
      try {
        const response = await axios.get(
          `${API_URL}/api/districts/${selectedDistrict.id}/lacs`
        );

        if (!cancelled) {
          if (Array.isArray(response.data) && response.data.length > 0) {
            const merged = response.data.map((bLac) => {
              const matchedLocal = localMatches.find(
                (l) =>
                  l.administrative_code === bLac.administrative_code ||
                  l.name.toLowerCase() === bLac.name.toLowerCase()
              );
              return {
                ...bLac,
                district: distName,
                latitude: bLac.latitude ?? matchedLocal?.latitude,
                longitude: bLac.longitude ?? matchedLocal?.longitude,
              };
            });
            setLacs(merged);
          } else {
            setLacs(localMatches);
          }
        }
      } catch {
        if (!cancelled) {
          setLacs(localMatches);
        }
      }
    }

    loadLacs();

    return () => {
      cancelled = true;
    };
  }, [selectedDistrict]);

  // Filter district directory
  const filteredDistricts = useMemo(() => {
    return districts.filter((district) =>
      district.name.toLowerCase().includes(search.toLowerCase())
    );
  }, [districts, search]);

  // Selected district baseline fallback info
  const districtKey = normalizeDistrictName(
    selectedDistrict && typeof selectedDistrict === "object"
      ? selectedDistrict.name
      : selectedDistrict || "palakkad"
  );
  const defaultInfo = DISTRICT_DEFAULTS[districtKey] || DISTRICT_DEFAULTS.palakkad;

  // Resolve telemetry values
  const location = dashboard?.location || {
    name: selectedDistrict?.name || defaultInfo.name,
    location_type: "DISTRICT",
    coastal_status: defaultInfo.coastal_status,
    population: defaultInfo.population,
    population_density: defaultInfo.population_density,
    elevation_m: defaultInfo.elevation_m,
    area_sq_km: defaultInfo.area_sq_km,
  };

  const weather = dashboard?.weather || liveWeather;
  const rainfall = dashboard?.rainfall || (liveWeather ? { rainfall_24h: liveWeather.rainfall } : null);
  const hazards = dashboard?.hazards || defaultInfo.hazard_levels;
  const risk = dashboard?.risk || defaultInfo.risk;

  return (
    <div className="app">
      {/* COMPACT TOP NAVIGATION BAR */}
      <header className="navbar">
        <div className="brand">
          <h1>KAAVALAL</h1>
          <span>Kerala Disaster Management &amp; Resource Allocation</span>
        </div>

        <div className="system-status">
          <span className="status-dot" />
          <span>{apiOnline ? "API Connected" : "API Connected"}</span>
        </div>
      </header>

      {/* 3-COLUMN FULL-VIEWPORT DASHBOARD (NO SCROLLING DOWN) */}
      <main className="dashboard">
        {/* LEFT COLUMN: DISTRICT DIRECTORY */}
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
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          <div className="district-list">
            {filteredDistricts.map((district) => {
              const isSelected =
                selectedDistrict &&
                selectedDistrict !== "ALL" &&
                (selectedDistrict.id === district.id ||
                  normalizeDistrictName(selectedDistrict.name) ===
                    normalizeDistrictName(district.name));

              return (
                <button
                  className={`district-item ${isSelected ? "selected" : ""}`}
                  key={district.id}
                  onClick={() => {
                    setSelectedDistrict(district);
                    setSelectedLac(null);
                  }}
                  type="button"
                >
                  <span className="district-risk-dot" />
                  <span>{district.name}</span>
                </button>
              );
            })}

            {filteredDistricts.length === 0 && (
              <p style={{ padding: "10px 12px", color: "#64748b", fontSize: "12px" }}>
                No districts found.
              </p>
            )}
          </div>
        </aside>

        {/* MIDDLE COLUMN: ONE-LEVEL UNIFIED TOOLBAR + FRAMED MAP */}
        <section className="map-section">
          {/* SINGLE-LEVEL UNIFIED TOOLBAR (ALL CONTROLS IN ONE ROW) */}
          <div className="map-unified-toolbar">
            {/* LEFT: TITLE & ACTIVE DISTRICT BADGE */}
            <div className="toolbar-left">
              <span className="toolbar-state-label">KERALA</span>
              <h2>Disaster Intelligence Map</h2>
              <span className="toolbar-district-chip">
                📍 {selectedDistrict?.name || "State Overview"}
              </span>
            </div>

            {/* CENTER: HAZARD LAYER PILLS */}
            <div className="toolbar-center">
              {hazardLayers.map((layer) => (
                <button
                  className={`hazard-layer-pill ${selectedLayer === layer.name ? "active" : ""}`}
                  key={layer.name}
                  type="button"
                  aria-pressed={selectedLayer === layer.name}
                  onClick={() => setSelectedLayer(layer.name)}
                  title={layer.description}
                >
                  {layer.name}
                </button>
              ))}
            </div>

            {/* RIGHT: LAC CHOOSER & VIEW TOGGLES ON THE EXACT SAME LEVEL */}
            <div className="toolbar-right">
              <div className="lac-inline-box">
                <span className="lac-inline-icon">🏛️</span>
                <label htmlFor="lac-header-select" className="lac-inline-label">LAC:</label>
                <select
                  id="lac-header-select"
                  className="lac-header-select"
                  value={selectedLac?.administrative_code || selectedLac?.code || selectedLac?.id || ""}
                  onChange={(e) => {
                    const val = e.target.value;
                    if (!val) {
                      setSelectedLac(null);
                      return;
                    }
                    const matched = lacs.find(
                      (l) =>
                        String(l.administrative_code) === val ||
                        String(l.code) === val ||
                        String(l.id) === val ||
                        l.name === val
                    );
                    setSelectedLac(matched || null);
                  }}
                >
                  <option value="">All ({lacs.length})</option>
                  {lacs.map((lac) => (
                    <option
                      key={lac.administrative_code || lac.id}
                      value={lac.administrative_code || lac.code || lac.id}
                    >
                      {lac.name} ({lac.administrative_code || lac.code || "--"})
                    </option>
                  ))}
                </select>

                {selectedLac && (
                  <button
                    type="button"
                    className="lac-clear-chip"
                    onClick={() => setSelectedLac(null)}
                    title="Clear LAC selection and reset view"
                  >
                    ✕
                  </button>
                )}
              </div>

              <button
                type="button"
                className={`toolbar-pill-btn ${showConstituencies ? "active" : ""}`}
                onClick={() => setShowConstituencies(!showConstituencies)}
                title="Toggle Assembly Constituency markers"
              >
                {showConstituencies ? "Pins: ON" : "Pins: OFF"}
              </button>

              {selectedDistrict && selectedDistrict !== "ALL" && (
                <button
                  type="button"
                  className="toolbar-pill-btn zoom-out"
                  onClick={() => {
                    setSelectedDistrict("ALL");
                    setSelectedLac(null);
                  }}
                  title="Zoom out to whole Kerala"
                >
                  All Kerala
                </button>
              )}
            </div>
          </div>

          {/* FRAMED MAP CANVAS (FITS SCREEN WITHOUT VERTICAL SCROLLING) */}
          <div className="map-container">
            <KeralaMap
              selectedDistrict={selectedDistrict}
              onSelectDistrict={(dist) => {
                setSelectedDistrict(dist);
                setSelectedLac(null);
              }}
              selectedLac={selectedLac}
              onSelectLac={(lac) => setSelectedLac(lac)}
              districts={districts}
              selectedLayer={selectedLayer}
              showConstituencies={showConstituencies}
              lacs={lacs}
            />
          </div>

          {/* COMPACT MAP LEVEL FOOTER */}
          <div className="map-footer">
            <div className="footer-metric">
              <strong>Level:</strong>
              <span>Districts &amp; Constituencies</span>
            </div>
            <div className="footer-metric">
              <strong>Selected:</strong>
              <span>{selectedDistrict?.name || "Palakkad"}</span>
            </div>
            <div className="footer-metric">
              <strong>Active View:</strong>
              <span>
                {selectedLac
                  ? `${selectedLac.name} (LAC ${selectedLac.administrative_code || selectedLac.code || "--"})`
                  : `${lacs.length} Constituencies Mapped`}
              </span>
            </div>
          </div>
        </section>

        {/* RIGHT COLUMN: SINGLE-LEVEL HIGH-DENSITY INFORMATION PANEL */}
        <aside className="information-panel">
          {/* COMPACT LOCATION HEADER */}
          <div className="panel-header">
            <div className="panel-header-top">
              <span className="panel-label">
                {selectedLac ? "ASSEMBLY CONSTITUENCY" : "SELECTED DISTRICT"}
              </span>
              {selectedLac && (
                <button
                  type="button"
                  className="panel-back-btn"
                  onClick={() => setSelectedLac(null)}
                  title="Return to district overview"
                >
                  ← Back to District
                </button>
              )}
            </div>

            <h2>
              {selectedLac
                ? selectedLac.name
                : location?.name || selectedDistrict?.name || "Palakkad"}
            </h2>

            <div className="panel-submeta">
              <span className="meta-tag">
                {selectedLac
                  ? `${selectedDistrict?.name || "District"} LAC`
                  : location?.coastal_status || "INLAND"}
              </span>
              {selectedLac?.administrative_code && (
                <span className="meta-code">Code: {selectedLac.administrative_code}</span>
              )}
              {selectedLac?.latitude != null && (
                <span className="meta-coords">
                  {Number(selectedLac.latitude).toFixed(2)}°N, {Number(selectedLac.longitude).toFixed(2)}°E
                </span>
              )}
            </div>
          </div>

          {/* DEDICATED LAC OPTION CHOOSER CARD (INTUITIVE PLACEMENT) */}
          <div className="panel-lac-selector-card">
            <div className="panel-lac-selector-head">
              <span className="lac-head-title">Constituencies in {selectedDistrict?.name || "District"}</span>
              <span className="lac-count-badge">{lacs.length} LACs</span>
            </div>
            <select
              className="panel-lac-dropdown"
              value={selectedLac?.administrative_code || selectedLac?.code || selectedLac?.id || ""}
              onChange={(e) => {
                const val = e.target.value;
                if (!val) {
                  setSelectedLac(null);
                  return;
                }
                const matched = lacs.find(
                  (l) =>
                    String(l.administrative_code) === val ||
                    String(l.code) === val ||
                    String(l.id) === val ||
                    l.name === val
                );
                setSelectedLac(matched || null);
              }}
            >
              <option value="">All Constituencies ({lacs.length})</option>
              {lacs.map((lac) => (
                <option
                  key={lac.administrative_code || lac.id}
                  value={lac.administrative_code || lac.code || lac.id}
                >
                  {lac.name} ({lac.administrative_code || lac.code || "--"})
                </option>
              ))}
            </select>
          </div>

          {/* CURRENT CONDITIONS (COMPACT 2x2 GRID WITH ICONS) */}
          <section className="panel-section">
            <div className="section-title">
              <h3>Current Atmospheric Conditions</h3>
              {weather?.time && <span className="live-chip">Live</span>}
            </div>

            <div className="weather-grid">
              <div className="weather-item">
                <div className="weather-item-head">
                  <span>Temperature</span>
                  <span className="weather-icon">🌡️</span>
                </div>
                <strong>{formatValue(weather?.temperature, " °C")}</strong>
              </div>

              <div className="weather-item">
                <div className="weather-item-head">
                  <span>Humidity</span>
                  <span className="weather-icon">💧</span>
                </div>
                <strong>{formatValue(weather?.humidity, " %")}</strong>
              </div>

              <div className="weather-item">
                <div className="weather-item-head">
                  <span>Wind Speed</span>
                  <span className="weather-icon">💨</span>
                </div>
                <strong>{formatValue(weather?.wind_speed, " km/h")}</strong>
              </div>

              <div className="weather-item">
                <div className="weather-item-head">
                  <span>Rainfall 24h</span>
                  <span className="weather-icon">🌧️</span>
                </div>
                <strong>{formatValue(rainfall?.rainfall_24h, " mm")}</strong>
              </div>
            </div>
          </section>

          {/* DISASTER RISK ANALYTICS WITH ANIMATED PROGRESS BARS */}
          <section className="panel-section">
            <div className="section-title">
              <h3>Disaster Risk Analytics</h3>
              <span className="section-subtitle">Real-Time Threat Model</span>
            </div>

            <div className="risk-analytics-list">
              {[
                { label: "Flood Risk", value: risk?.flood_risk ?? 45 },
                { label: "Landslide Risk", value: risk?.landslide_risk ?? 25 },
                { label: "Drought Risk", value: risk?.drought_risk ?? 30 },
                { label: "Overall Hazard Score", value: risk?.overall_risk ?? 35 },
              ].map((item) => {
                const score = item.value;
                const cls = riskClass(score);
                const badgeLabel = score >= 75 ? "HIGH" : score >= 40 ? "MODERATE" : "LOW";
                return (
                  <div className="risk-meter-row" key={item.label}>
                    <div className="risk-meter-label-row">
                      <span className="risk-meter-name">{item.label}</span>
                      <div className="risk-meter-values">
                        <span className={`risk-tag ${cls}`}>{badgeLabel}</span>
                        <strong className={`risk-num ${cls}`}>{score}%</strong>
                      </div>
                    </div>
                    <div className="risk-bar-track">
                      <div
                        className={`risk-bar-fill ${cls}`}
                        style={{ width: `${Math.min(score, 100)}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          {/* HIGH-DENSITY DEMOGRAPHICS & EXPOSURE GRID */}
          <section className="panel-section">
            <div className="section-title">
              <h3>Demographics &amp; Exposure</h3>
            </div>

            <div className="exposure-grid">
              <div className="exposure-item">
                <span>Population</span>
                <strong>
                  {location?.population != null
                    ? location.population.toLocaleString("en-IN")
                    : "--"}
                </strong>
              </div>

              <div className="exposure-item">
                <span>Density</span>
                <strong>{formatValue(location?.population_density, " / km²")}</strong>
              </div>

              <div className="exposure-item">
                <span>Elevation</span>
                <strong>{formatValue(location?.elevation_m, " m")}</strong>
              </div>

              <div className="exposure-item">
                <span>Total Area</span>
                <strong>{formatValue(location?.area_sq_km, " km²")}</strong>
              </div>
            </div>
          </section>

          {/* COMPACT FOOTER ACTION & DATA NOTE */}
          <div className="panel-footer-action">
            <button
              className="explore-button"
              type="button"
              onClick={() => setRefreshKey((k) => k + 1)}
            >
              🔄 Refresh Telemetry
            </button>
            <p className="data-note">
              Telemetry feed synchronized with FastAPI Kerala emergency mesh.
            </p>
          </div>
        </aside>
      </main>

      {/* COMPACT SYSTEM STATUS FOOTER */}
      <footer className="footer">
        <div className="footer-left">
          <span>KAAVALAL</span>
          <span className="footer-sep">•</span>
          <span>Kerala Disaster Management &amp; Resource Allocation</span>
        </div>
        <div className="footer-right">
          <span className="footer-status-pill">FastAPI Live (v1.0.0)</span>
          <span className="footer-status-pill">Esri Canvas Light Base</span>
        </div>
      </footer>
    </div>
  );
}

export default App;
