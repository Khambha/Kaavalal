import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import "./Home.css";

const API_URL = "http://127.0.0.1:8000";

// ======================================================
// EMERGENCY CONTACTS
// ======================================================

const CONTACTS = [
  {
    label: "National Emergency",
    number: "112",
    note: "Police, fire and ambulance",
  },
  {
    label: "Police",
    number: "100",
    note: "Police control room",
  },
  {
    label: "Fire & Rescue",
    number: "101",
    note: "Fire brigade",
  },
  {
    label: "Ambulance",
    number: "108",
    note: "Medical emergency",
  },
  {
    label: "Disaster Helpline",
    number: "1077",
    note: "District control room (add your STD code)",
  },
  {
    label: "State Control Room",
    number: "1070",
    note: "Kerala disaster management",
  },
  {
    label: "KSDMA Control Room",
    number: "0471-2331639",
    note: "State disaster management",
  },
  {
    label: "Women Helpline",
    number: "1091",
    note: "24x7 support",
  },
];

// ======================================================
// LIVE WEATHER COMPONENT
// ======================================================

function LiveWeather() {
  const [districts, setDistricts] = useState([]);
  const [districtId, setDistrictId] = useState("");

  const [lacs, setLacs] = useState([]);
  const [lacId, setLacId] = useState("");

  const [weather, setWeather] = useState(null);

  const [loadingDistricts, setLoadingDistricts] = useState(true);
  const [loadingLacs, setLoadingLacs] = useState(false);
  const [loadingWeather, setLoadingWeather] = useState(false);

  const [districtError, setDistrictError] = useState("");
  const [lacError, setLacError] = useState("");
  const [weatherError, setWeatherError] = useState("");

  // Find the selected district by its actual database ID.
  const district = districts.find(
    (item) => String(item.id) === String(districtId)
  );

  // Find the selected LAC by its actual database ID.
  const selectedLac = lacs.find(
    (item) => String(item.id) === String(lacId)
  );

  // ====================================================
  // 1. LOAD DISTRICTS
  // ====================================================

  useEffect(() => {
    let cancelled = false;

    async function loadDistricts() {
      setLoadingDistricts(true);
      setDistrictError("");

      try {
        const response = await axios.get(
          `${API_URL}/api/districts`,
          {
            timeout: 15000,
          }
        );

        if (cancelled) return;

        const data = Array.isArray(response.data)
          ? response.data
          : [];

        console.log("Districts loaded:", data);

        setDistricts(data);

        if (data.length === 0) {
          setDistrictId("");
          setDistrictError(
            "No districts were found in the database."
          );
          return;
        }

        // Select Wayanad by default.
        // If Wayanad is not available, select the first district.
        const defaultDistrict = data.find(
          (item) =>
            String(item.name || "").trim().toUpperCase() ===
            "WAYANAD"
        );

        const initialDistrict = defaultDistrict || data[0];

        setDistrictId(String(initialDistrict.id));
      } catch (error) {
        console.error("District loading error:", error);

        if (!cancelled) {
          setDistrictError(
            error.response?.data?.detail ||
              error.message ||
              "Unable to load districts. Check the backend."
          );
        }
      } finally {
        if (!cancelled) {
          setLoadingDistricts(false);
        }
      }
    }

    loadDistricts();

    return () => {
      cancelled = true;
    };
  }, []);

  // ====================================================
  // 2. LOAD LACS WHEN DISTRICT CHANGES
  // ====================================================

  useEffect(() => {
    if (!districtId) {
      setLacs([]);
      setLacId("");
      setLoadingLacs(false);
      setLacError("");
      return;
    }

    let cancelled = false;

    async function loadLacs() {
      setLoadingLacs(true);
      setLacs([]);
      setLacId("");
      setLacError("");

      try {
        const response = await axios.get(
          `${API_URL}/api/districts/${districtId}/lacs`,
          {
            timeout: 15000,
          }
        );

        if (cancelled) return;

        const data = Array.isArray(response.data)
          ? response.data
          : [];

        console.log(
          `LACs for district ${districtId}:`,
          data
        );

        setLacs(data);

        if (data.length === 0) {
          setLacError(
            "No LAC records were found for this district."
          );
        }
      } catch (error) {
        console.error("LAC loading error:", error);

        if (!cancelled) {
          setLacError(
            error.response?.data?.detail ||
              error.message ||
              "Unable to load constituencies."
          );
        }
      } finally {
        if (!cancelled) {
          setLoadingLacs(false);
        }
      }
    }

    loadLacs();

    return () => {
      cancelled = true;
    };
  }, [districtId]);

  // ====================================================
  // 3. LOAD OPENWEATHER WEATHER DATA
  // ====================================================

  // When an LAC is selected, use its database ID.
  // Otherwise, use the selected district's database ID.
  const weatherLocationId = lacId
    ? selectedLac?.id
    : district?.id;

  useEffect(() => {
    if (!weatherLocationId) {
      setWeather(null);
      setLoadingWeather(false);
      setWeatherError("");
      return;
    }

    let cancelled = false;

    async function loadWeather() {
      setLoadingWeather(true);
      setWeather(null);
      setWeatherError("");

      try {
        // This endpoint uses the OpenWeather integration
        // configured in the FastAPI backend.
        const response = await axios.get(
          `${API_URL}/api/weather/${weatherLocationId}`,
          {
            timeout: 20000,
          }
        );

        if (cancelled) return;

        console.log(
          "Weather response:",
          response.data
        );

        setWeather(response.data);
      } catch (error) {
        console.error("Weather loading error:", error);

        if (!cancelled) {
          setWeather(null);

          setWeatherError(
            error.response?.data?.detail ||
              error.message ||
              "Unable to retrieve weather."
          );
        }
      } finally {
        if (!cancelled) {
          setLoadingWeather(false);
        }
      }
    }

    loadWeather();

    return () => {
      cancelled = true;
    };
  }, [weatherLocationId]);

  // ====================================================
  // 4. WEATHER DISPLAY VALUES
  // ====================================================

  const place = selectedLac
    ? `${selectedLac.name} LAC`
    : district
      ? `${district.name} district`
      : "Kerala";

  const temperature = weather?.temperature ?? null;
  const feelsLike = weather?.feels_like ?? null;
  const humidity = weather?.humidity ?? null;
  const pressure = weather?.pressure ?? null;
  const visibility = weather?.visibility ?? null;

  // OpenWeather reports wind speed in metres per second.
  // Convert to kilometres per hour for display.
  const windSpeed =
    weather?.wind_speed != null
      ? Number(weather.wind_speed) * 3.6
      : null;

  // OpenWeather may provide rainfall for the last hour.
  const rainfall =
    weather?.rainfall_1h ??
    weather?.rainfall ??
    null;

  const condition =
    weather?.weather_condition ||
    weather?.description ||
    (rainfall != null && Number(rainfall) > 0
      ? "Rain"
      : "Current weather conditions");

  const weatherIcon = weather?.weather_icon;

  const weatherIconUrl = weatherIcon
    ? `https://openweathermap.org/img/wn/${weatherIcon}@2x.png`
    : "";

  const stats = [
    {
      label: "Temperature",
      value:
        temperature != null
          ? Number(temperature).toFixed(1)
          : "--",
      unit: "°C",
    },
    {
      label: "Feels Like",
      value:
        feelsLike != null
          ? Number(feelsLike).toFixed(1)
          : "--",
      unit: "°C",
    },
    {
      label: "Humidity",
      value: humidity != null ? humidity : "--",
      unit: "%",
    },
    {
      label: "Wind Speed",
      value:
        windSpeed != null
          ? windSpeed.toFixed(1)
          : "--",
      unit: "km/h",
    },
    {
      label: "Precipitation",
      value:
        rainfall != null
          ? Number(rainfall).toFixed(1)
          : "--",
      unit: "mm",
    },
    {
      label: "Pressure",
      value:
        pressure != null
          ? pressure
          : "--",
      unit: "hPa",
    },
  ];

  // ====================================================
  // 5. LIVE WEATHER USER INTERFACE
  // ====================================================

  return (
    <section className="home-section" id="weather">
      <div className="section-head">
        <h2>Live Weather</h2>

        <div className="weather-selects">
          {/* DISTRICT DROPDOWN */}

          <select
            className="weather-select"
            value={districtId}
            onChange={(event) => {
              setDistrictId(event.target.value);
              setLacId("");
            }}
            aria-label="Choose district"
            disabled={
              loadingDistricts ||
              districts.length === 0
            }
          >
            {loadingDistricts ? (
              <option value="">
                Loading districts...
              </option>
            ) : districts.length === 0 ? (
              <option value="">
                No districts available
              </option>
            ) : (
              districts.map((item) => (
                <option
                  key={item.id}
                  value={String(item.id)}
                >
                  {item.name}
                </option>
              ))
            )}
          </select>

          {/* LAC DROPDOWN */}

          <select
            className="weather-select"
            value={lacId}
            onChange={(event) => {
              setLacId(event.target.value);
            }}
            aria-label="Choose constituency"
            disabled={
              !districtId ||
              loadingLacs ||
              lacs.length === 0
            }
          >
            <option value="">
              {loadingLacs
                ? "Loading constituencies..."
                : `All constituencies (${lacs.length})`}
            </option>

            {lacs.map((lac) => (
              <option
                key={lac.id}
                value={String(lac.id)}
              >
                {lac.name}
                {lac.administrative_code
                  ? ` (${lac.administrative_code})`
                  : ""}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* WEATHER PANEL */}

      <div className="weather-panel">
        <div className="weather-panel-head">
          <h3>
            Current conditions near {place}
          </h3>

          {weather && !loadingWeather && (
            <span className="live-chip">
              Live
            </span>
          )}
        </div>

        <p className="weather-source">
          {weather?.source || "OpenWeather"}
        </p>

        {/* DISTRICT ERROR */}

        {districtError && (
          <p className="section-note error">
            {districtError}
          </p>
        )}

        {/* LAC ERROR */}

        {lacError && (
          <p className="section-note error">
            {lacError}
          </p>
        )}

        {/* WEATHER LOADING */}

        {loadingWeather && (
          <p className="section-note">
            Loading weather for {place}...
          </p>
        )}

        {/* WEATHER ERROR */}

        {weatherError && !loadingWeather && (
          <p className="section-note error">
            {weatherError}
          </p>
        )}

        {/* WEATHER DETAILS */}

        {weather && !loadingWeather && (
          <>
            <div className="weather-now">
              {weatherIconUrl && (
                <img
                  src={weatherIconUrl}
                  alt={condition}
                  width="64"
                  height="64"
                  onError={(event) => {
                    event.currentTarget.style.display =
                      "none";
                  }}
                />
              )}

              <div>
                <h3>
                  {temperature != null
                    ? `${Number(temperature).toFixed(1)}°C`
                    : "--"}
                </h3>

                <p>{condition}</p>
              </div>
            </div>

            <div className="weather-cards">
              {stats.map((item) => (
                <div
                  className="weather-card"
                  key={item.label}
                >
                  <span>{item.label}</span>

                  <strong>
                    {item.value}{" "}
                    <small>{item.unit}</small>
                  </strong>
                </div>
              ))}
            </div>

            {visibility != null && (
              <p className="section-note">
                Visibility:{" "}
                {(Number(visibility) / 1000).toFixed(1)}
                {" "}km
              </p>
            )}

            {weather.time && (
              <p className="section-note">
                Observation time: {weather.time}
              </p>
            )}

            {weather.recorded_at && (
              <p className="section-note">
                Weather timestamp:{" "}
                {new Date(
                  Number(weather.recorded_at) * 1000
                ).toLocaleString()}
              </p>
            )}
          </>
        )}
      </div>
    </section>
  );
}

// ======================================================
// EMERGENCY CONTACT COMPONENT
// ======================================================

function EmergencyContacts() {
  return (
    <section
      className="home-section"
      id="emergency"
    >
      <div className="section-head">
        <h2>Emergency Contact</h2>
      </div>

      <div className="contact-grid">
        {CONTACTS.map((contact) => (
          <a
            className="contact-card"
            key={contact.label}
            href={`tel:${contact.number.replace(
              /[^0-9]/g,
              ""
            )}`}
          >
            <span className="contact-label">
              {contact.label}
            </span>

            <strong>{contact.number}</strong>

            <span className="contact-note">
              {contact.note}
            </span>
          </a>
        ))}
      </div>
    </section>
  );
}

// ======================================================
// MAIN HOME PAGE
// ======================================================

export default function Home() {
  return (
    <div className="kaavalal-home">
      {/* NAVIGATION */}

      <nav className="home-nav">
        <Link
          to="/"
          className="home-brand"
        >
          <span className="brand-dot"></span>
          കാവലാൾ
        </Link>

        <div className="home-nav-links">
          <a
            href="#home"
            className="active"
          >
            Home
          </a>

          <a href="#weather">
            Live Weather
          </a>

          <a href="#emergency">
            Emergency Contact
          </a>
        </div>

        <div className="nav-actions">
          <Link
            to="/login"
            className="login-btn"
          >
            Login
          </Link>

          <Link
            to="/signup"
            className="get-started"
          >
            Sign Up
          </Link>
        </div>
      </nav>

      {/* HERO SECTION */}

      <section
        className="home-hero"
        id="home"
      >
        <div className="hero-background"></div>

        <div className="hero-content">
          <div className="hero-label">
            <span></span>
            KERALA DISASTER MANAGEMENT PLATFORM
          </div>

          <h1>
            Every Second
            <br />
            <span>Saves</span> a Life
          </h1>

          <p>
            Monitor disasters, access weather information,
            and connect people with emergency response teams.
          </p>

          <a
            href="#emergency"
            className="explore-button"
          >
            Emergency Contact <span>→</span>
          </a>
        </div>
      </section>

      {/* LIVE WEATHER */}

      <LiveWeather />

      {/* EMERGENCY CONTACTS */}

      <EmergencyContacts />

      {/* FOOTER */}

      <footer className="home-about">
        <div>
          <span className="about-dot"></span>
          <strong>കാവലാൾ</strong>
        </div>

        <p>
          A safer Kerala through connected response.
        </p>
      </footer>
    </div>
  );
}
