import { useEffect, useState } from "react";
import axios from "axios";
import "./seekhelp.css";

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

export default function SeekHelp() {
  const [form, setForm] = useState(INITIAL_FORM);
  const [districts, setDistricts] = useState([]);
  const [lacs, setLacs] = useState([]);
  const [requests, setRequests] = useState([]);
  const [image, setImage] = useState(null);
  const [loading, setLoading] = useState(false);
  const [fetchingLacs, setFetchingLacs] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    loadDistricts();
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

      if (form.latitude && form.longitude) {
        payload.append("latitude", form.latitude);
        payload.append("longitude", form.longitude);
      }

      if (image) {
        payload.append("image", image);
      }

      await axios.post(API_URL + "/", payload, authConfig());

      setSuccess(
        "Your help request has been submitted successfully."
      );

      setForm(INITIAL_FORM);
      setLacs([]);
      setImage(null);

      const fileInput = document.getElementById("help-image");

      if (fileInput) {
        fileInput.value = "";
      }

      await loadRequests();
    } catch (err) {
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
          <h1>Seek Help</h1>
          <p>
            Describe your situation so the response team can understand
            what assistance you need.
          </p>
        </div>

        <div className="seek-help-icon" aria-hidden="true">
          SOS
        </div>
      </header>

      <div className="seek-help-notice">
        <strong>Emergency notice</strong>
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
          <h2>01. Emergency Location</h2>
          <p>Tell us where assistance is needed.</p>

          <div className="seek-help-grid">
            <label>
              District <span>*</span>

              <select
                name="district"
                value={form.district}
                onChange={handleChange}
                required
              >
                <option value="">Select district</option>

                {districts.map((district) => (
                  <option key={district} value={district}>
                    {district}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Legislative Assembly Constituency (LAC) <span>*</span>

              <select
                name="lac"
                value={form.lac}
                onChange={handleChange}
                required
                disabled={!form.district || fetchingLacs}
              >
                <option value="">
                  {!form.district
                    ? "Select a district first"
                    : fetchingLacs
                    ? "Loading LACs..."
                    : "Select LAC"}
                </option>

                {lacs.map((lac) => (
                  <option key={lac} value={lac}>
                    {lac}
                  </option>
                ))}
              </select>
            </label>

            <label className="full-width">
              Locality, address, or landmark <span>*</span>

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
              <strong>Share your current location</strong>
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
              Latitude
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
              Longitude
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
          <h2>02. Emergency Details</h2>
          <p>Tell us what kind of help is required.</p>

          <div className="seek-help-grid">
            <label>
              Emergency type <span>*</span>

              <select
                name="emergency_type"
                value={form.emergency_type}
                onChange={handleChange}
                required
              >
                <option value="">Select emergency</option>

                {EMERGENCY_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Urgency level <span>*</span>

              <select
                name="urgency"
                value={form.urgency}
                onChange={handleChange}
                required
              >
                {URGENCY_LEVELS.map((level) => (
                  <option key={level} value={level}>
                    {level}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Number of people affected <span>*</span>

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
            <legend>Does anyone need special assistance?</legend>

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

                {item}
              </label>
            ))}
          </fieldset>

          <label className="description-label">
            Describe your situation <span>*</span>

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
            <strong>Upload an image (optional)</strong>
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

          <button type="submit" disabled={loading}>
            {loading ? "Submitting..." : "Submit Help Request"}
          </button>
        </div>
      </form>

      <section className="my-help-requests">
        <div className="my-help-heading">
          <div>
            <h2>My Help Requests</h2>
            <p>Review the requests submitted through your account.</p>
          </div>

          <button
            type="button"
            className="secondary-button"
            onClick={loadRequests}
          >
            Refresh
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
                    {request.status}
                  </span>
                </div>

                <p>
                  <strong>Location:</strong>{" "}
                  {request.location_description}
                </p>

                <p>
                  <strong>District:</strong> {request.district}
                  {" · "}
                  <strong>LAC:</strong> {request.lac}
                </p>

                <p>
                  <strong>Urgency:</strong> {request.urgency}
                </p>

                <p>{request.situation_description}</p>

                {request.responder_notes && (
                  <p>
                    <strong>Response team update:</strong>{" "}
                    {request.responder_notes}
                  </p>
                )}

                <small>
                  Submitted:{" "}
                  {request.created_at
                    ? new Date(request.created_at).toLocaleString()
                    : "Date unavailable"}
                </small>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}