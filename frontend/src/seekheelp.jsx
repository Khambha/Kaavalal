import { useEffect, useState } from "react";
import axios from "axios";
import "./seekhelp.css";
import { t, localeName } from "./services/i18n";
import { queueOfflineRequest } from "./services/offlineQueue";

const API_URL = "http://127.0.0.1:8000/api/help-requests";

const EMERGENCY_TYPES = [
  "Flood",
  "Landslide",
  "Medical Emergency",
  "Trapped Person",
  "Fire",
  "Missing Person",
  "Evacuation",
  "Food and Water",
  "Shelter",
  "Other",
];

const URGENCY_LEVELS = ["Critical", "High", "Medium", "Low"];

const INITIAL_FORM = {
  district: "",
  lac: "",
  location_description: "",
  latitude: "",
  longitude: "",
  emergency_type: "",
  people_affected: "1",
  special_assistance: [],
  urgency: "High",
  situation_description: "",
};

function getToken() {
  return (
    localStorage.getItem("access_token") ||
    localStorage.getItem("token") ||
    ""
  );
}

function authConfig() {
  const token = getToken();

  return {
    headers: token
      ? { Authorization: `Bearer ${token}` }
      : {},
  };
}

function initialForm(mode, lac) {
  const form = { ...INITIAL_FORM, district: lac?.district || "", lac: lac?.name || "" };
  return mode === "sos" ? { ...form, emergency_type: "Other", urgency: "Critical", situation_description: "SOS emergency: " } : form;
}

export default function SeekHelp({ mode = "help", language = "en", defaultLac = null }) {
  const [form, setForm] = useState(() => initialForm(mode, defaultLac));
  const [districts, setDistricts] = useState([]);
  const [lacs, setLacs] = useState([]);
  const [requests, setRequests] = useState([]);
  const [image, setImage] = useState(null);
  const [loading, setLoading] = useState(false);
  const [fetchingLacs, setFetchingLacs] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [histories, setHistories] = useState({});

  async function toggleHistory(requestId) {
    if (histories[requestId]) { setHistories(v => ({ ...v, [requestId]: null })); return; }
    try {
      const response = await axios.get(`${API_URL}/my/${requestId}/history`, authConfig());
      setHistories(v => ({ ...v, [requestId]: response.data || [] }));
    } catch { setError("Unable to load request history. Please try again."); }
  }

  useEffect(() => { setForm(initialForm(mode, defaultLac)); setError(""); setSuccess(""); }, [mode, defaultLac?.id]);

  useEffect(() => {
    loadDistricts();
    if (defaultLac?.district) loadLacs(defaultLac.district);
    loadRequests();
  }, []);

  async function loadDistricts() {
    try {
      const response = await axios.get(`${API_URL}/districts`);

      setDistricts(response.data.districts || []);
    } catch (err) {
      console.error("Failed to load help-request districts:", err);
      setError("Unable to load districts. Check that the backend is running.");
    }
  }

  async function loadLacs(district) {
    setLacs([]);

    if (!district) {
      return;
    }

    setFetchingLacs(true);

    try {
      const response = await axios.get(
        `${API_URL}/lacs/${encodeURIComponent(district)}`
      );

      setLacs(response.data.lacs || []);
    } catch (err) {
      console.error("Failed to load LACs:", err);
      setError("Unable to load LACs for this district. Please try again.");
    } finally {
      setFetchingLacs(false);
    }
  }

  async function loadRequests() {
    try {
      const response = await axios.get(
        `${API_URL}/my`,
        authConfig()
      );

      setRequests(response.data || []);
    } catch (err) {
      if (err.response?.status === 401) {
        setError("Please sign in to view your help requests.");
      }
    }
  }

  async function saveIncidentOffline() {
    setError(""); setSuccess("");
    if (!getToken()) { setError("Please sign in before submitting a help request."); return; }
    if (!form.district || !form.lac || !form.location_description.trim() || !form.emergency_type || !form.urgency || !form.situation_description.trim() || form.situation_description.trim().length < 10) {
      setError(language === "ml" ? "ഓഫ്‌ലൈൻ ആയി സൂക്ഷിക്കുന്നതിന് മുമ്പ് ആവശ്യമായ വിവരങ്ങൾ പൂരിപ്പിക്കുക." : "Complete the required fields before saving this request offline."); return;
    }
    const requestId = window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const payload = { district: form.district, lac: form.lac, location_description: form.location_description,
      emergency_type: form.emergency_type, people_affected: form.people_affected,
      special_assistance: form.special_assistance.join(", "), urgency: form.urgency,
      situation_description: form.situation_description, client_request_id: requestId };
    if (form.latitude && form.longitude) { payload.latitude = form.latitude; payload.longitude = form.longitude; }
    if (image) payload.image = image;
    setLoading(true);
    try {
      await queueOfflineRequest({ id: requestId, type: "incident", payload, queued_at: new Date().toISOString() });
      setSuccess(language === "ml" ? "അഭ്യർത്ഥന ഈ ഉപകരണത്തിൽ സൂക്ഷിച്ചു. കണക്ഷൻ ലഭിക്കുമ്പോൾ അയയ്ക്കും." : "Request saved on this device. It will sync when the connection returns.");
      setForm(initialForm(mode, defaultLac)); setLacs(defaultLac?.district ? lacs : []); setImage(null);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }

  function handleChange(event) {
    const { name, value } = event.target;

    if (name === "district") {
      setForm((previous) => ({
        ...previous,
        district: value,
        lac: "",
      }));

      setError("");
      setSuccess("");
      loadLacs(value);

      return;
    }

    setForm((previous) => ({
      ...previous,
      [name]: value,
    }));
  }

  function handleAssistanceChange(event) {
    const { value, checked } = event.target;

    setForm((previous) => {
      const current = previous.special_assistance;

      return {
        ...previous,
        special_assistance: checked
          ? [...current, value]
          : current.filter((item) => item !== value),
      };
    });
  }

  function detectLocation() {
    setError("");
    setSuccess("");

    if (!navigator.geolocation) {
      setError("Location detection is not supported by this browser.");
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        setForm((previous) => ({
          ...previous,
          latitude: position.coords.latitude.toFixed(6),
          longitude: position.coords.longitude.toFixed(6),
        }));

        setSuccess("Location detected successfully.");
      },
      () => {
        setError(
          "Unable to detect location. Please allow location access or enter it manually."
        );
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 0,
      }
    );
  }

  async function handleSubmit(event) {
    event.preventDefault();

    setError("");
    setSuccess("");

    if (!getToken()) {
      setError("Please sign in before submitting a help request.");
      return;
    }

    if (!form.district || !form.lac) {
      setError("Please select your district and LAC.");
      return;
    }

    if (
      (form.latitude && !form.longitude) ||
      (!form.latitude && form.longitude)
    ) {
      setError("Please provide both GPS coordinates or leave both empty.");
      return;
    }

    if (
      form.latitude &&
      (
        Number(form.latitude) < -90 ||
        Number(form.latitude) > 90 ||
        !Number.isFinite(Number(form.latitude))
      )
    ) {
      setError("Latitude must be between -90 and 90.");
      return;
    }

    if (
      form.longitude &&
      (
        Number(form.longitude) < -180 ||
        Number(form.longitude) > 180 ||
        !Number.isFinite(Number(form.longitude))
      )
    ) {
      setError("Longitude must be between -180 and 180.");
      return;
    }

    setLoading(true);
    const clientRequestId = window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    let offlinePayload = null;

    try {
      const payload = new FormData();

      payload.append("district", form.district);
      payload.append("lac", form.lac);
      payload.append(
        "location_description",
        form.location_description
      );
      payload.append("emergency_type", form.emergency_type);
      payload.append("people_affected", form.people_affected);
      payload.append("special_assistance", form.special_assistance.join(", "));
      payload.append("urgency", form.urgency);
      payload.append(
        "situation_description",
        form.situation_description
      );
      payload.append("client_request_id", clientRequestId);

      if (form.latitude && form.longitude) {
        payload.append("latitude", form.latitude);
        payload.append("longitude", form.longitude);
      }

      if (image) {
        payload.append("image", image);
      }

      offlinePayload = Object.fromEntries(payload.entries());
      const response = await axios.post(API_URL + "/", payload, authConfig());

      setSuccess(language === "ml"
        ? `HELP-${response.data.id} ആയി സ്വീകരിച്ചു. ${response.data.lac}, ${response.data.district} പ്രദേശത്തെ രക്ഷാസംഘത്തിന് കൈമാറി.${response.data.eta_estimate_minutes ? ` കണക്കാക്കിയ പ്രതികരണ സമയം ഏകദേശം ${response.data.eta_estimate_minutes} മിനിറ്റ്.` : ""} ഇത് ഏകദേശ കണക്കാണ്; ഉറപ്പല്ല.`
        : `Acknowledged as HELP-${response.data.id}. Routed to the response team for ${response.data.lac}, ${response.data.district}.${response.data.eta_estimate_minutes ? ` Estimated response window: about ${response.data.eta_estimate_minutes} minutes.` : ""} This is an estimate, not a guarantee.`);

      setForm(initialForm(mode, defaultLac));
      setLacs([]);
      setImage(null);

      const fileInput = document.getElementById("help-image");

      if (fileInput) {
        fileInput.value = "";
      }

      await loadRequests();
    } catch (err) {
      if (!err.response && offlinePayload) {
        try {
          await queueOfflineRequest({ id: clientRequestId, type: "incident", payload: offlinePayload, queued_at: new Date().toISOString() });
          setSuccess("Your request was saved on this device and will sync when the connection returns.");
          setForm(initialForm(mode, defaultLac)); setLacs(defaultLac?.district ? lacs : []); setImage(null);
          return;
        } catch (queueError) {
          setError(queueError.message || "Could not save this request offline. Keep this page open and try again when connected.");
          return;
        }
      }
      const detail = err.response?.data?.detail;

      setError(
        typeof detail === "string"
          ? detail
          : "Unable to submit the request. Please check your information and try again."
      );
    } finally {
      setLoading(false);
    }
  }

  function getStatusClass(status) {
    return String(status || "Submitted")
      .toLowerCase()
      .replace(/\s+/g, "-");
  }

  return (
    <div className="seek-help-page">
      <header className="seek-help-header">
        <div>
          <p className="seek-help-eyebrow">KAAVALAL EMERGENCY SERVICES</p>
          <h1>{t(mode === "sos" ? "Emergency / SOS Response" : "Report an Incident", language)}</h1>
          <p>
            {mode === "sos" ? (language === "ml" ? "നിങ്ങളുടെ പ്രദേശത്തെ രക്ഷാസംഘത്തിന് അടിയന്തര സഹായ അഭ്യർത്ഥന അയയ്ക്കുക." : "Send an urgent request to the rescue team covering your location.") : (language === "ml" ? "സംഭവവും ആവശ്യമായ സഹായവും പ്രാദേശിക രക്ഷാസംഘത്തെ അറിയിക്കുക." : "Describe the incident so the response team can understand what assistance is needed.")}
          </p>
        </div>

        <div className="seek-help-icon" aria-hidden="true">
          SOS
        </div>
      </header>

      <div className="seek-help-notice">
        <strong>{t("Emergency notice",language)}</strong>
        <p>
          If you are in immediate danger, contact local emergency
          services directly. Submitting this form does not guarantee
          immediate assistance.
        </p>
      </div>

      {error && (
        <div className="seek-help-message error" role="alert">
          {error}
        </div>
      )}

      {success && (
        <div className="seek-help-message success" role="status">
          {success}
        </div>
      )}

      <form className="seek-help-form" onSubmit={handleSubmit}>
        <section className="seek-help-section">
          <h2>{t("01. Emergency Location",language)}</h2>
          <p>{t("Tell us where assistance is needed.",language)}</p>

          <div className="seek-help-grid">
            <label>
              {t("District",language)} <span>*</span>

              <select
                name="district"
                value={form.district}
                onChange={handleChange}
                required
              >
                <option value="">{t("Select district",language)}</option>

                {districts.map((district) => (
                  <option key={district} value={district}>
                    {district}
                  </option>
                ))}
              </select>
            </label>

            <label>
              {t("Legislative Assembly Constituency (LAC)",language)} <span>*</span>

              <select
                name="lac"
                value={form.lac}
                onChange={handleChange}
                required
                disabled={!form.district || fetchingLacs}
              >
                <option value="">
                  {!form.district
                    ? (language === "ml" ? "ആദ്യം ജില്ല തിരഞ്ഞെടുക്കുക" : "Select a district first")
                    : fetchingLacs
                    ? (language === "ml" ? "മണ്ഡലങ്ങൾ ലോഡ് ചെയ്യുന്നു…" : "Loading LACs...")
                    : t("Select LAC",language)}
                </option>

                {lacs.map((lac) => (
                  <option key={lac} value={lac}>
                    {lac}
                  </option>
                ))}
              </select>
            </label>

            <label className="full-width">
              {t("Locality, address, or landmark",language)} <span>*</span>

              <input
                name="location_description"
                value={form.location_description}
                onChange={handleChange}
                placeholder="House name, street, village, or nearby landmark"
                maxLength={500}
                required
              />
            </label>
          </div>

          <div className="seek-help-gps">
            <div>
              <strong>{t("Share your current location",language)}</strong>
              <p>
                Optional. Allow your browser to access your location.
              </p>
            </div>

            <button
              type="button"
              className="secondary-button"
              onClick={detectLocation}
            >
              Detect GPS Location
            </button>
          </div>

          <div className="seek-help-grid">
            <label>
              {t("Latitude",language)}
              <input
                type="number"
                step="any"
                name="latitude"
                value={form.latitude}
                onChange={handleChange}
                placeholder="Optional"
                min="-90"
                max="90"
              />
            </label>

            <label>
              {t("Longitude",language)}
              <input
                type="number"
                step="any"
                name="longitude"
                value={form.longitude}
                onChange={handleChange}
                placeholder="Optional"
                min="-180"
                max="180"
              />
            </label>
          </div>
        </section>

        <section className="seek-help-section">
          <h2>02. {t("Emergency Details",language)}</h2>
          <p>{t("Tell us what kind of help is required.",language)}</p>

          <div className="seek-help-grid">
            <label>
              {t("Emergency type",language)} <span>*</span>

              <select
                name="emergency_type"
                value={form.emergency_type}
                onChange={handleChange}
                required
              >
                <option value="">Select emergency</option>

                {EMERGENCY_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {t(type,language)}
                  </option>
                ))}
              </select>
            </label>

            <label>
              {t("Urgency level",language)} <span>*</span>

              <select
                name="urgency"
                value={form.urgency}
                onChange={handleChange}
                required
              >
                {URGENCY_LEVELS.map((level) => (
                  <option key={level} value={level}>
                    {t(level,language)}
                  </option>
                ))}
              </select>
            </label>

            <label>
              {t("Number of people affected",language)} <span>*</span>

              <input
                type="number"
                name="people_affected"
                min="1"
                max="10000"
                value={form.people_affected}
                onChange={handleChange}
                required
              />
            </label>
          </div>

          <fieldset className="seek-help-assistance">
            <legend>{t("Does anyone need special assistance?",language)}</legend>

            {[
              "Children",
              "Elderly people",
              "People with disabilities",
              "Medical assistance",
              "Pregnant people",
            ].map((item) => (
              <label key={item} className="checkbox-option">
                <input
                  type="checkbox"
                  value={item}
                  checked={form.special_assistance.includes(item)}
                  onChange={handleAssistanceChange}
                />

                {t(item,language)}
              </label>
            ))}
          </fieldset>

          <label className="description-label">
            {t("Describe your situation",language)} <span>*</span>

            <textarea
              name="situation_description"
              value={form.situation_description}
              onChange={handleChange}
              minLength={10}
              maxLength={5000}
              rows={6}
              placeholder="Explain what happened, who needs help, and what assistance is required."
              required
            />

            <small>
              {form.situation_description.length}/5000 characters
            </small>
          </label>

          <label className="upload-area" htmlFor="help-image">
            <strong>{t("Upload an image (optional)",language)}</strong>
            <span>JPEG, PNG, or WebP. Maximum size: 5 MB.</span>

            <input
              id="help-image"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={(event) => {
                const selected = event.target.files?.[0] || null;

                if (selected && selected.size > 5 * 1024 * 1024) {
                  setImage(null);
                  event.target.value = "";
                  setError("Image size must not exceed 5 MB.");
                  return;
                }

                setError("");
                setImage(selected);
              }}
            />

            {image && <span>Selected: {image.name}</span>}
          </label>
        </section>

        <div className="seek-help-submit">
          <p>
            Your report will be visible to authorized personnel
            responsible for handling emergency requests.
          </p>

          <p className="offline-storage-note">{language === "ml" ? "ഇന്റർനെറ്റ് കുറവാണെങ്കിൽ അഭ്യർത്ഥന ഉപകരണത്തിൽ സൂക്ഷിക്കാം. പങ്കിടുന്ന ഉപകരണത്തിൽ വ്യക്തിഗത വിവരങ്ങൾ സൂക്ഷിക്കുമ്പോൾ ശ്രദ്ധിക്കുക." : "On a weak connection, save the request on this device and sync it later. Avoid storing personal details on a shared device."}</p>

          <button type="submit" disabled={loading}>
            {loading ? (language === "ml" ? "അയയ്ക്കുന്നു..." : "Submitting...") : t("Submit Help Request",language)}
          </button>
          <button type="button" className="secondary-button" onClick={saveIncidentOffline} disabled={loading}>{language === "ml" ? "ഉപകരണത്തിൽ സൂക്ഷിക്കുക" : "Save on this device"}</button>
        </div>
      </form>

      <section className="my-help-requests">
        <div className="my-help-heading">
          <div>
            <h2>{t("My Help Requests",language)}</h2>
            <p>{t("Review the requests submitted through your account.",language)}</p>
          </div>

          <button
            type="button"
            className="secondary-button"
            onClick={loadRequests}
          >
            {t("Refresh",language)}
          </button>
        </div>

        {requests.length === 0 ? (
          <div className="empty-requests">
            No help requests found.
          </div>
        ) : (
          <div className="help-request-list">
            {requests.map((request) => (
              <article className="help-request-card" key={request.id}>
                <div className="request-card-heading">
                  <div>
                    <span className="request-id">
                      HELP-{request.id}
                    </span>

                    <h3>{request.emergency_type}</h3>
                  </div>

                  <span
                    className={`request-status ${getStatusClass(
                      request.status
                    )}`}
                  >
                    {t(request.status,language)}
                  </span>
                </div>

                <p>
                    <strong>{t("Location:",language)}</strong>{" "}
                  {request.location_description}
                </p>

                <p><strong>{language === "ml" ? "സ്ഥിതി:" : "Status:"}</strong> {t(request.status,language)}{request.eta_estimate_minutes ? ` · ${language === "ml" ? "കണക്കാക്കിയ പ്രതികരണ സമയം" : "Estimated response window"}: ${request.eta_estimate_minutes} ${language === "ml" ? "മിനിറ്റ്" : "minutes"}` : ""}</p>

                <p>
                  <strong>{t("District",language)}:</strong> {request.district}
                  {" · "}
                  <strong>LAC:</strong> {request.lac}
                </p>

                <p>
                  <strong>{t("Urgency:",language)}</strong> {t(request.urgency,language)}
                </p>

                <p>{request.situation_description}</p>

                {request.responder_notes && (
                  <p>
                    <strong>{t("Response team update:",language)}</strong>{" "}
                    {request.responder_notes}
                  </p>
                )}

                <small>
                  Submitted:{" "}
                  {request.created_at
                    ? new Date(request.created_at).toLocaleString(localeName(language))
                    : "Date unavailable"}
                </small>
                <button type="button" className="secondary-button" onClick={() => toggleHistory(request.id)}>{histories[request.id] ? t("Hide status history",language) : t("View status history",language)}</button>
                {histories[request.id] && <ol className="request-status-history">{histories[request.id].map(item=><li key={item.id}><b>{t(item.status,language)}</b><span>{t(item.note,language)}</span><small>{new Date(item.created_at).toLocaleString(localeName(language))}</small></li>)}</ol>}
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
