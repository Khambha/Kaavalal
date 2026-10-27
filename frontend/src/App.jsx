import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import "./index.css";
import "./dashboard-ui/dashboard.css";
import "./dashboard-ui/integration.css";
import KeralaMap from "./dashboard-ui/KeralaMap";
import Icon from "./dashboard-ui/Icons";
import RiskMeter from "./dashboard-ui/RiskMeter";
import { normalizeDistrictName, getDistrictLayerScore, getRiskBand } from "./dashboard-ui/riskScale";
import lacData from "./lac_locations.json";
import SeekHelp from "./seekheelp";
import ShelterRequests from "./pages/ShelterRequests";
import CitizenPortal, { CitizenAlerts, CitizenInformation } from "./pages/CitizenPortal";
import { t } from "./services/i18n";
import { flushOfflineRequests, listOfflineRequests } from "./services/offlineQueue";
import "./pages/citizen-portal.css";
import "./pages/request-tracking.css";

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
const DISTRICT_DEFAULTS = {
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
  const [lacWeatherLoading, setLacWeatherLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  // null = still connecting, true = reachable, false = unreachable
  const [apiOnline, setApiOnline] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const [lacs, setLacs] = useState([]);
  const [shelters, setShelters] = useState([]);
  const [activeView, setActiveView] = useState("citizen");
  const [language, setLanguage] = useState(localStorage.getItem("kaavalal_language") === "ml" ? "ml" : "en");

  useEffect(() => {
    let active = true;
    const loadShelters = () => axios.get(`${API_URL}/api/shelters`, { headers: { "Cache-Control": "no-cache" } })
      .then(response => { if (active) setShelters(response.data || []); })
      .catch(() => { /* Keep the last public shelter list during brief API outages. */ });
    loadShelters();
    const interval = window.setInterval(loadShelters, 30000);
    window.addEventListener("focus", loadShelters);
    return () => {
      active = false;
      window.clearInterval(interval);
      window.removeEventListener("focus", loadShelters);
    };
  }, []);

  useEffect(() => {
    if (sessionStorage.getItem("kaavalal_startup_location_resolved")) return;
    sessionStorage.setItem("kaavalal_startup_location_resolved", "1");
    const records = (lacData.constituencies || []).filter(l => Number.isFinite(Number(l.latitude)) && Number.isFinite(Number(l.longitude)));
    function applyLac(lac) {
      if (!lac) return false;
      const district = initialDistricts.find(d => normalizeDistrictName(d.name) === normalizeDistrictName(lac.district));
      if (!district) return false;
      setSelectedDistrict(district);
      setSelectedLac({ id: Number(lac.lac_code), name: lac.lac_name, administrative_code: lac.lac_code, district: lac.district, latitude: Number(lac.latitude), longitude: Number(lac.longitude), location_type: "LAC" });
      return true;
    }
    function nearest(lat, lng) {
      if (!Number.isFinite(lat) || !Number.isFinite(lng) || !records.length) return null;
      const radians = value => value * Math.PI / 180;
      return records.reduce((best, lac) => {
        const dLat = radians(Number(lac.latitude) - lat); const dLng = radians(Number(lac.longitude) - lng);
        const a = Math.sin(dLat/2)**2 + Math.cos(radians(lat))*Math.cos(radians(Number(lac.latitude)))*Math.sin(dLng/2)**2;
        const distance = 6371 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        return !best || distance < best.distance ? { lac, distance } : best;
      }, null)?.lac;
    }
    async function savedArea() {
      const token = localStorage.getItem("token") || sessionStorage.getItem("token");
      if (!token) return;
      try {
        const response = await fetch(`${API_URL}/api/auth/me`, { headers: { Authorization: `Bearer ${token}` } });
        if (!response.ok) return;
        const profile = await response.json();
        applyLac(records.find(l => normalizeDistrictName(l.district) === normalizeDistrictName(profile.district) && normalizeDistrictName(l.lac_name) === normalizeDistrictName(profile.nearest_lac)));
      } catch { /* Keep the dashboard's default location if the profile cannot be loaded. */ }
    }
    if (navigator.geolocation) navigator.geolocation.getCurrentPosition(position => { if (!applyLac(nearest(position.coords.latitude, position.coords.longitude))) savedArea(); }, savedArea, { enableHighAccuracy: false, timeout: 7000, maximumAge: 300000 });
    else savedArea();
  }, []);

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

  // Load live weather for the selected LAC centroid, or the district when no
  // constituency is selected. LACs use the same Open-Meteo backend provider.
  useEffect(() => {
    if (!selectedDistrict || selectedDistrict === "ALL" || !selectedDistrict.id) {
      setLiveWeather(null);
      setLacWeatherLoading(false);
      return;
    }

    let cancelled = false;
    setLiveWeather(null);
    setLacWeatherLoading(Boolean(selectedLac));

    async function fetchLiveWeather() {
      try {
        const lacCode = selectedLac?.administrative_code || selectedLac?.code || selectedLac?.id;
        const endpoint = selectedLac
          ? `${API_URL}/api/districts/${selectedDistrict.id}/lacs/${encodeURIComponent(lacCode)}/weather`
          : `${API_URL}/api/districts/${selectedDistrict.id}/weather`;
        const params = selectedLac ? {
          latitude: selectedLac.latitude,
          longitude: selectedLac.longitude,
        } : undefined;
        const response = await axios.get(endpoint, { params });
        if (!cancelled && response.data) {
          setLiveWeather(response.data);
          setApiOnline(true);
        }
      } catch {
        if (!cancelled) {
          setLiveWeather(null);
        }
      } finally {
        if (!cancelled) setLacWeatherLoading(false);
      }
    }

    fetchLiveWeather();

    return () => {
      cancelled = true;
    };
  }, [selectedDistrict, selectedLac, refreshKey]);

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

  const weather = selectedLac ? liveWeather : (liveWeather || dashboard?.weather);
  const rainfall = liveWeather ? { rainfall_24h: liveWeather.rainfall } : dashboard?.rainfall;
  const risk = dashboard?.risk || null;

  const isStateView = selectedDistrict === "ALL";
  const districtName = selectedDistrict?.name || location?.name || "Palakkad";
  const panelLabel = selectedLac
    ? "Assembly constituency"
    : isStateView
      ? "Statewide view"
      : "Selected district";
  const panelTitle = selectedLac ? selectedLac.name : isStateView ? "Kerala" : districtName;

  const lacValue = selectedLac?.administrative_code || selectedLac?.code || selectedLac?.id || "";
  function handleLacChange(e) {
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
  }

  const readings = [
    { label: "Temperature", icon: "thermometer", value: weather?.temperature, unit: " °C" },
    { label: "Humidity", icon: "droplet", value: weather?.humidity, unit: " %" },
    { label: "Wind speed", icon: "wind", value: weather?.wind_speed, unit: " km/h" },
    { label: liveWeather ? "Precipitation" : "Rainfall, 24 h", icon: "rain", value: rainfall?.rainfall_24h, unit: " mm" },
  ];
  const hasReadings = readings.some((r) => r.value !== null && r.value !== undefined && r.value !== "");

  const apiClass = apiOnline === null ? "is-pending" : apiOnline ? "is-online" : "is-offline";
  const apiLabel = apiOnline === null ? "Connecting…" : apiOnline ? "API connected" : "API offline";

  return (
    <div className="app dashboard-ui">
      <header className="navbar">
        <div className="brand">
          <h1 className="wordmark">Kaavalal</h1>
          <span className="wordmark-ml" lang="ml">കാവലാൾ</span>
          <span className="tagline">Kerala disaster management &amp; resource allocation</span>
        </div>

        <nav className="portal-nav" aria-label="Citizen navigation">
          <button className={activeView === "citizen" ? "active" : ""} onClick={() => setActiveView("citizen")}>{t("Citizen Portal",language)}</button>
          <button className={activeView === "dashboard" ? "active" : ""} onClick={() => setActiveView("dashboard")}>{t("Disaster Dashboard",language)}</button>
          <button className="portal-sos" onClick={() => setActiveView("sos")}>SOS</button>
          <button className="portal-language" onClick={() => { const next = language === "en" ? "ml" : "en"; setLanguage(next); localStorage.setItem("kaavalal_language",next); }} aria-label="Change language">{language === "en" ? "മലയാളം" : "English"}</button>
        </nav>
        <div className={`system-status ${apiClass}`} role="status">
          <span className="status-dot" aria-hidden="true" />
          {apiLabel}
        </div>
      </header>
      <OfflineSync language={language} />

      {activeView === "dashboard" ? <main className="dashboard">
        {/* DISTRICT LIST */}
        <aside className="district-sidebar" aria-label="Districts">
          <div className="sidebar-header">
            <h2>Districts</h2>
            <span className="count-chip">{filteredDistricts.length}</span>
          </div>

          <label className="district-search">
            <Icon name="search" size={15} />
            <input
              type="search"
              placeholder="Search districts"
              aria-label="Search districts"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </label>

          <p className="sidebar-caption">Dot and score show {selectedLayer.toLowerCase()}.</p>

          <div className="district-list">
            {filteredDistricts.map((district) => {
              const isSelected =
                selectedDistrict &&
                selectedDistrict !== "ALL" &&
                (selectedDistrict.id === district.id ||
                  normalizeDistrictName(selectedDistrict.name) ===
                    normalizeDistrictName(district.name));
              const score = getDistrictLayerScore(district.name, selectedLayer);
              const band = getRiskBand(score);

              return (
                <button
                  className={`district-item${isSelected ? " selected" : ""}`}
                  key={district.id}
                  onClick={() => {
                    setSelectedDistrict(district);
                    setSelectedLac(null);
                  }}
                  type="button"
                  aria-current={isSelected ? "true" : undefined}
                >
                  <span className="risk-dot" style={{ background: band.color }} aria-hidden="true" />
                  <span className="district-name">{district.name}</span>
                  <span className="district-score" title={`${selectedLayer}: ${band.label}`}>
                    {score}
                  </span>
                </button>
              );
            })}

            {filteredDistricts.length === 0 && (
              <p className="list-empty">No district matches “{search}”.</p>
            )}
          </div>
        </aside>

        {/* MAP */}
        <section className="map-section">
          <div className="map-toolbar">
            <nav className="crumbs" aria-label="Map location">
              <button
                type="button"
                className={`crumb${isStateView ? " is-current" : ""}`}
                onClick={() => {
                  setSelectedDistrict("ALL");
                  setSelectedLac(null);
                }}
                title="Show all of Kerala"
              >
                Kerala
              </button>
              {!isStateView && (
                <>
                  <span className="crumb-sep"><Icon name="chevron" size={14} /></span>
                  <button
                    type="button"
                    className={`crumb${selectedLac ? "" : " is-current"}`}
                    onClick={() => setSelectedLac(null)}
                  >
                    {selectedDistrict?.name}
                  </button>
                </>
              )}
              {selectedLac && (
                <>
                  <span className="crumb-sep"><Icon name="chevron" size={14} /></span>
                  <span className="crumb is-current">{selectedLac.name}</span>
                </>
              )}
            </nav>

            <div className="segmented" role="group" aria-label="Map layer">
              {hazardLayers.map((layer) => (
                <button
                  className={`segment${selectedLayer === layer.name ? " active" : ""}`}
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

            <button
              type="button"
              className="switch"
              role="switch"
              aria-checked={showConstituencies}
              onClick={() => setShowConstituencies(!showConstituencies)}
              title="Show or hide assembly constituency pins"
            >
              <span className="switch-track" aria-hidden="true">
                <span className="switch-thumb" />
              </span>
              Constituency pins
            </button>
          </div>

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
              shelters={shelters}
            />
          </div>
        </section>

        {/* DETAIL PANEL */}
        <aside className="information-panel" aria-label="Details">
          <div className="panel-scroll">
            <div className="panel-header">
              <div className="panel-header-top">
                <span className="panel-label">{panelLabel}</span>
                {selectedLac && (
                  <button
                    type="button"
                    className="panel-back-btn"
                    onClick={() => setSelectedLac(null)}
                  >
                    <Icon name="back" size={13} /> {selectedDistrict?.name}
                  </button>
                )}
              </div>

              <h2>{panelTitle}</h2>

              {!isStateView && (
                <div className="panel-submeta">
                  <span className="meta-tag">
                    {selectedLac ? `${selectedDistrict?.name || "District"} LAC` : location?.coastal_status || "INLAND"}
                  </span>
                  {selectedLac?.administrative_code && (
                    <span className="meta-text">Code {selectedLac.administrative_code}</span>
                  )}
                  {selectedLac?.latitude != null && (
                    <span className="meta-text">
                      {Number(selectedLac.latitude).toFixed(2)}°N, {Number(selectedLac.longitude).toFixed(2)}°E
                    </span>
                  )}
                </div>
              )}
            </div>

            {isStateView ? (
              <div className="panel-empty">
                <span className="panel-empty-icon"><Icon name="pointer" size={22} /></span>
                <h3>Pick a district</h3>
                <p>
                  Select a district on the map or from the list to see its current weather,
                  risk scores and population exposure.
                </p>
              </div>
            ) : (
              <>
                {selectedLac && (
                  <p className="panel-note">
                    Live weather is fetched for this LAC’s coordinates. Risk, population and terrain figures remain at {selectedDistrict?.name} district level.
                  </p>
                )}

                <div className="lac-picker">
                  <div className="lac-picker-head">
                    <label htmlFor="lac-select">Constituencies</label>
                    <span className="count-chip">{lacs.length}</span>
                  </div>
                  <select id="lac-select" value={lacValue} onChange={handleLacChange}>
                    <option value="">All constituencies ({lacs.length})</option>
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

                <section className="panel-section">
                  <div className="section-title">
                    <h3>{selectedLac ? "Current conditions near LAC" : "Current conditions"}</h3>
                    {weather?.time && <span className="live-chip">Live</span>}
                  </div>
                  {selectedLac && <p className="section-subtitle weather-source">{lacWeatherLoading ? "Loading LAC weather…" : liveWeather?.source ? `${liveWeather.source} · ${liveWeather.latitude?.toFixed?.(3)}, ${liveWeather.longitude?.toFixed?.(3)}` : "LAC weather is currently unavailable"}</p>}

                  {!loading && !lacWeatherLoading && !hasReadings && (
                    <p className="panel-note is-inline">
                      {selectedLac ? "No live weather readings are available for this LAC right now. Refresh to try again." : "No live readings for this district. Check the API connection, then refresh."}
                    </p>
                  )}

                  <div className="tile-grid">
                    {readings.map((r) => {
                      const empty = r.value === null || r.value === undefined || r.value === "";
                      return (
                        <div className={`tile${empty ? " is-empty" : ""}`} key={r.label}>
                          <span className="tile-label">
                            <Icon name={r.icon} size={14} /> {r.label}
                          </span>
                          {(lacWeatherLoading || loading) && !hasReadings ? (
                            <span className="skeleton" />
                          ) : (
                            <strong className="tile-value">
                              {empty ? "—" : r.value}
                              {!empty && <small>{r.unit}</small>}
                            </strong>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </section>

                <section className="panel-section">
                  <div className="section-title">
                    <h3>{selectedLac ? "District disaster risk" : "Disaster risk"}</h3>
                    <span className="section-subtitle">{selectedLac ? `${selectedDistrict?.name} district data` : risk ? "From API" : "Unavailable"}</span>
                  </div>
                  <div className="meter-list">
                    <RiskMeter label="Overall hazard" value={risk?.overall_risk ?? null} featured />
                    <RiskMeter label="Flood" value={risk?.flood_risk ?? null} />
                    <RiskMeter label="Landslide" value={risk?.landslide_risk ?? null} />
                    <RiskMeter label="Drought" value={risk?.drought_risk ?? null} />
                  </div>
                </section>

                <section className="panel-section">
                  <div className="section-title">
                    <h3>{selectedLac ? "District population and terrain" : "Population and terrain"}</h3>
                  </div>
                  <div className="tile-grid">
                    <div className="tile">
                      <span className="tile-label">Population</span>
                      <strong className="tile-value">
                        {location?.population != null
                          ? location.population.toLocaleString("en-IN")
                          : "—"}
                      </strong>
                    </div>
                    <div className="tile">
                      <span className="tile-label">Density</span>
                      <strong className="tile-value">
                        {location?.population_density ?? "—"}
                        <small> /km²</small>
                      </strong>
                    </div>
                    <div className="tile">
                      <span className="tile-label">Elevation</span>
                      <strong className="tile-value">
                        {location?.elevation_m ?? "—"}
                        <small> m</small>
                      </strong>
                    </div>
                    <div className="tile">
                      <span className="tile-label">Area</span>
                      <strong className="tile-value">
                        {location?.area_sq_km ?? "—"}
                        <small> km²</small>
                      </strong>
                    </div>
                  </div>
                </section>
              </>
            )}
          </div>

          {!isStateView && (
            <div className="panel-footer-action">
              <button
                className="explore-button"
                type="button"
                disabled={loading}
                onClick={() => setRefreshKey((k) => k + 1)}
              >
                <span className={loading ? "is-spinning" : undefined}>
                  <Icon name="refresh" size={15} />
                </span>
                {loading ? "Refreshing…" : "Refresh readings"}
              </button>
            </div>
          )}
        </aside>
      </main> : <div className="citizen-view">
        {activeView === "citizen" && <CitizenPortal selectedLac={selectedLac} language={language} onNavigate={setActiveView} />}
        {activeView === "alerts" && <CitizenAlerts language={language} onBack={() => setActiveView("citizen")} />}
        {activeView === "information" && <CitizenInformation language={language} onBack={() => setActiveView("citizen")} />}
        {(activeView === "help" || activeView === "sos") && <SeekHelp mode={activeView} language={language} defaultLac={selectedLac} />}
        {activeView === "shelter" && <ShelterRequests shelters={shelters} language={language} />}
      </div>}

      {activeView === "dashboard" && <footer className="footer">
        <span>Some values are sample data and are not official measurements.</span>
        <span>Basemap: Esri World Light Gray</span>
      </footer>}
    </div>
  );
}

export default App;

function OfflineSync({ language = "en" }) {
  const [offline, setOffline] = useState(!navigator.onLine);
  const [pending, setPending] = useState(0);
  const [synced, setSynced] = useState(0);
  async function refresh() { try { setPending((await listOfflineRequests()).length); } catch { setPending(0); } }
  async function sync() {
    setOffline(!navigator.onLine);
    try { const result = await flushOfflineRequests(); setPending(result.pending ?? (await listOfflineRequests()).length); if (result.synced) setSynced(result.synced); }
    catch { refresh(); }
  }
  useEffect(() => {
    const onOnline = () => { setOffline(false); sync(); };
    const onOffline = () => setOffline(true);
    const onOutbox = event => { refresh(); if (event.detail?.synced) setSynced(event.detail.synced); if (event.detail?.queued && navigator.onLine) sync(); };
    window.addEventListener("online", onOnline); window.addEventListener("offline", onOffline); window.addEventListener("kaavalal-outbox-changed", onOutbox);
    refresh(); if (navigator.onLine) sync();
    return () => { window.removeEventListener("online", onOnline); window.removeEventListener("offline", onOffline); window.removeEventListener("kaavalal-outbox-changed", onOutbox); };
  }, []);
  if (!offline && pending === 0 && synced === 0) return null;
  return <div className={`citizen-offline-banner ${offline ? "offline" : ""}`} role="status"><span>{offline ? (language === "ml" ? "ഓഫ്‌ലൈൻ മോഡ്" : "Offline mode") : pending ? `${pending} request${pending===1?"":"s"} waiting to sync` : `${synced} request${synced===1?"":"s"} synced successfully`}</span>{offline&&<small>{t("Waiting for connection. Request will sync when online.",language)}</small>}{navigator.onLine&&pending>0&&<button onClick={sync}>{language === "ml" ? "ഇപ്പോൾ സിങ്ക് ചെയ്യുക" : "Sync now"}</button>}</div>;
}
