import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import AuthLayout, { Icon, RoleToggle } from "./AuthLayout";
import lacData from "../lac_locations.json";

const API_URL = "http://127.0.0.1:8000";

const DISTRICTS = [
  "Thiruvananthapuram",
  "Kollam",
  "Pathanamthitta",
  "Alappuzha",
  "Kottayam",
  "Idukki",
  "Ernakulam",
  "Thrissur",
  "Palakkad",
  "Malappuram",
  "Kozhikode",
  "Wayanad",
  "Kannur",
  "Kasaragod",
];

const DISTRICT_ALIASES = {
  trivandrum: "thiruvananthapuram",
  trichur: "thrissur",
  eranakulam: "ernakulam",
  wynad: "wayanad",
};

const normalize = (value) => {
  const normalized = String(value || "")
    .trim()
    .toLowerCase()
    .replace(/\bdistrict\b/g, "")
    .replace(/[^a-z]/g, "");
  return DISTRICT_ALIASES[normalized] || normalized;
};

function getDistrict(lac) {
  return (
    lac.district ??
    lac.district_name ??
    lac.districtName ??
    lac.District ??
    ""
  );
}

function getLacName(lac) {
  return (
    lac.lac_name ??
    lac.lacName ??
    lac.constituency_name ??
    lac.constituency ??
    lac.name ??
    ""
  );
}

function getLacCode(lac, index) {
  return (
    lac.lac_code ??
    lac.lacCode ??
    lac.code ??
    `${getLacName(lac)}-${index}`
  );
}

function extractLacs(data) {
  if (Array.isArray(data)) return data;

  if (Array.isArray(data?.constituencies)) {
    return data.constituencies;
  }

  if (Array.isArray(data?.lacs)) {
    return data.lacs;
  }

  if (Array.isArray(data?.lac_locations)) {
    return data.lac_locations;
  }

  if (Array.isArray(data?.features)) {
    return data.features.map((feature) => ({
      ...feature.properties,
      district:
        feature.properties?.district ??
        feature.properties?.DISTRICT ??
        feature.properties?.district_name,
    }));
  }

  return [];
}

function Field({ icon, children }) {
  return (
    <div className="field">
      <span className="field-icon">
        <Icon name={icon} />
      </span>
      {children}
    </div>
  );
}

function PasswordField({ icon = "lock", ...props }) {
  const [show, setShow] = useState(false);

  return (
    <Field icon={icon}>
      <input
        {...props}
        type={show ? "text" : "password"}
        autoComplete="new-password"
        required
      />

      <button
        type="button"
        className="eye"
        onClick={() => setShow((previous) => !previous)}
        aria-label={show ? "Hide password" : "Show password"}
      >
        <Icon name={show ? "eye" : "eyeoff"} size={16} />
      </button>
    </Field>
  );
}

export default function Signup() {
  const navigate = useNavigate();

  const [role, setRole] = useState("citizen");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [districts, setDistricts] = useState(DISTRICTS);
  const [districtRows, setDistrictRows] = useState([]);
  const [lacOptions, setLacOptions] = useState([]);
  const [lacLoading, setLacLoading] = useState(false);

  const [form, setForm] = useState({
    full_name: "",
    email: "",
    password: "",
    confirm: "",
    district: "",
    nearest_lac: "",
    organization_code: "",
    rescuer_id: "",
  });

  const allLacs = useMemo(() => {
    return extractLacs(lacData)
      .map((lac, index) => ({
        ...lac,
        _name: String(getLacName(lac)).trim(),
        _district: String(getDistrict(lac)).trim(),
        _code: getLacCode(lac, index),
      }))
      .filter((lac) => lac._name && lac._district);
  }, []);

  useEffect(() => {
    let active = true;
    fetch(`${API_URL}/api/districts`)
      .then((response) => {
        if (!response.ok) throw new Error("District directory unavailable");
        return response.json();
      })
      .then((rows) => {
        if (!active || !Array.isArray(rows) || rows.length === 0) return;
        setDistrictRows(rows);
        setDistricts(rows.map((district) => district.name));
      })
      .catch(() => { /* Keep the bundled district directory if the API is offline. */ });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!form.district) {
      setLacOptions([]);
      setLacLoading(false);
      return undefined;
    }

    let active = true;
    const selectedDistrict = normalize(form.district);
    const fallbackOptions = allLacs
      .filter((lac) => normalize(lac._district) === selectedDistrict)
      .sort((a, b) => a._name.localeCompare(b._name));
    const districtRow = districtRows.find(
      (district) => normalize(district.name) === selectedDistrict
    );

    if (!districtRow?.id) {
      setLacOptions(fallbackOptions);
      setLacLoading(false);
      return undefined;
    }

    setLacOptions([]);
    setLacLoading(true);
    fetch(`${API_URL}/api/districts/${districtRow.id}/lacs`)
      .then((response) => {
        if (!response.ok) throw new Error("LAC directory unavailable");
        return response.json();
      })
      .then((rows) => {
        if (!active) return;
        const databaseOptions = (Array.isArray(rows) ? rows : []).map((lac, index) => ({
          ...lac,
          _name: String(lac.name || "").trim(),
          _district: districtRow.name,
          _code: lac.administrative_code || lac.id || `${lac.name}-${index}`,
        })).filter((lac) => lac._name);
        setLacOptions(databaseOptions.length ? databaseOptions : fallbackOptions);
      })
      .catch(() => {
        if (active) setLacOptions(fallbackOptions);
      })
      .finally(() => {
        if (active) setLacLoading(false);
      });

    return () => { active = false; };
  }, [form.district, districtRows, allLacs]);

  function update(event) {
    const { name, value } = event.target;

    setForm((previous) => ({
      ...previous,
      [name]: value,
    }));

    setError("");
  }

  function changeRole(nextRole) {
    setRole(nextRole);
    setError("");
  }

  function changeDistrict(event) {
    setForm((previous) => ({
      ...previous,
      district: event.target.value,
      nearest_lac: "",
    }));

    setError("");
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");

    if (form.password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }

    if (form.password !== form.confirm) {
      setError("Passwords do not match.");
      return;
    }

    if (!form.district) {
      setError("Please select your district.");
      return;
    }

    if (!form.nearest_lac) {
      setError("Please select your nearest LAC.");
      return;
    }

    if (
      role === "rescuer" &&
      !form.organization_code.trim()
    ) {
      setError("Organization code is required for rescuers.");
      return;
    }

    if (role === "rescuer" && !form.rescuer_id.trim()) {
      setError("Rescuer ID is required.");
      return;
    }

    const body = {
      full_name: form.full_name.trim(),
      email: form.email.trim(),
      password: form.password,
      role,
      district: form.district,
      nearest_lac: form.nearest_lac,
    };

    if (role === "rescuer") {
      body.organization_code = form.organization_code
        .trim()
        .toUpperCase();

      body.rescuer_id = form.rescuer_id.trim();
    }

    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/api/auth/signup`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        const detail = Array.isArray(data.detail)
          ? data.detail.map((item) => item.msg).join(", ")
          : data.detail;

        throw new Error(detail || "Registration failed.");
      }

      if (role === "rescuer") {
        window.alert(
          "Registration submitted successfully! Your rescuer account is awaiting administrator approval."
        );
      } else {
        window.alert(
          "Account created successfully! Please log in with your email and password."
        );
      }

      navigate("/login");
    } catch (err) {
      setError(
        err.message ||
          "Unable to connect to the backend. Please try again."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthLayout variant="signup" role={role}>
      <form className="form" onSubmit={handleSubmit}>
        <h1>Create Your Account</h1>

        <p className="sub">
          Join KAAVALAL and be a part of a safer Kerala.
        </p>

        <RoleToggle role={role} setRole={changeRole} />

        <Field icon="user">
          <input
            name="full_name"
            type="text"
            placeholder="Full Name"
            value={form.full_name}
            onChange={update}
            autoComplete="name"
            required
          />
        </Field>

        <Field icon="mail">
          <input
            name="email"
            type="email"
            placeholder="Email Address"
            value={form.email}
            onChange={update}
            autoComplete="email"
            required
          />
        </Field>

        {role === "rescuer" && (
          <>
            <Field icon="user">
              <input
                name="organization_code"
                type="text"
                placeholder="Organization Code"
                value={form.organization_code}
                onChange={update}
                autoComplete="off"
                required
              />
            </Field>

            <Field icon="user">
              <input
                name="rescuer_id"
                type="text"
                placeholder="Rescuer ID"
                value={form.rescuer_id}
                onChange={update}
                autoComplete="off"
                required
              />
            </Field>
          </>
        )}

        <PasswordField
          name="password"
          placeholder="Password"
          value={form.password}
          onChange={update}
        />

        <PasswordField
          name="confirm"
          placeholder="Confirm Password"
          value={form.confirm}
          onChange={update}
        />

        <Field icon="pin">
          <select
            name="district"
            value={form.district}
            onChange={changeDistrict}
            required
          >
            <option value="">Select District</option>

            {DISTRICTS.map((district) => (
              <option key={district} value={district}>
                {district}
              </option>
            ))}
          </select>
        </Field>

        <Field icon="wave">
          <select
            name="nearest_lac"
            value={form.nearest_lac}
            onChange={update}
            disabled={!form.district}
            required
          >
            <option value="">
              {!form.district
                ? "Select district first"
                : lacLoading
                  ? "Loading LACs…"
                  : lacOptions.length > 0
                  ? "Select Nearest LAC"
                  : "No LACs found for this district"}
            </option>

            {lacOptions.map((lac) => (
              <option key={lac._code} value={lac._name}>
                {lac._name}
              </option>
            ))}
          </select>
        </Field>

        {form.district && !lacLoading && lacOptions.length === 0 && (
          <p className="msg error">
            No LAC records were returned for this district. Check the backend LAC directory.
          </p>
        )}

        {error && (
          <p className="msg error" role="alert">
            {error}
          </p>
        )}

        <button
          type="submit"
          className="primary"
          disabled={loading}
        >
          {loading
            ? "Creating Account..."
            : role === "rescuer"
              ? "Register as Rescuer"
              : "Sign Up"}
        </button>

        <p className="switch">
          Already have an account?{" "}
          <Link to="/login">Login</Link>
        </p>
      </form>
    </AuthLayout>
  );
}
