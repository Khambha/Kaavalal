// Single source of truth for risk bands, colours and district scores.
// Used by the map, the district list and the side panel so they always agree.

export function normalizeDistrictName(name) {
  if (!name) return "";
  let clean = String(name).trim().toLowerCase();
  clean = clean.replace(/\bdistrict\b/g, "").replace(/[^a-z]/g, "");
  if (clean === "trivandrum" || clean === "tvm") return "thiruvananthapuram";
  if (clean === "trichur") return "thrissur";
  if (clean === "eranakulam") return "ernakulam";
  if (clean === "wynad") return "wayanad";
  return clean;
}

// Teal -> yellow -> orange -> deep red. Hue and lightness both change between
// steps, and every place that uses a colour also shows the number or label.
export const RISK_BANDS = [
  { key: "low", label: "Low", min: 0, range: "0–39", color: "#55a896", ink: "#1b5a4d", tint: "#e0f1ed" },
  { key: "moderate", label: "Moderate", min: 40, range: "40–59", color: "#e8c24a", ink: "#6b5206", tint: "#fbf1cc" },
  { key: "high", label: "High", min: 60, range: "60–74", color: "#e7843b", ink: "#86390a", tint: "#fbe3cf" },
  { key: "severe", label: "Severe", min: 75, range: "75–100", color: "#b3282a", ink: "#7a1517", tint: "#f6d8d6" },
];

// Where one band ends and the next begins (drawn as ticks on the meters).
export const BAND_THRESHOLDS = RISK_BANDS.slice(1).map((b) => b.min);

export function getRiskBand(score) {
  if (score === null || score === undefined || Number.isNaN(Number(score))) return null;
  const n = Number(score);
  let found = RISK_BANDS[0];
  for (const band of RISK_BANDS) {
    if (n >= band.min) found = band;
  }
  return found;
}

// Sample scores used by the map and district list (not official measurements).
const DISTRICT_HAZARD_SCORES = {
  wayanad: { overall: 75, flood: 65, landslide: 92, drought: 15, rainfall: 82 },
  idukki: { overall: 78, flood: 72, landslide: 88, drought: 20, rainfall: 85 },
  pathanamthitta: { overall: 65, flood: 82, landslide: 68, drought: 15, rainfall: 75 },
  alappuzha: { overall: 70, flood: 90, landslide: 5, drought: 10, rainfall: 78 },
  ernakulam: { overall: 58, flood: 76, landslide: 15, drought: 15, rainfall: 70 },
  thrissur: { overall: 55, flood: 72, landslide: 28, drought: 20, rainfall: 68 },
  kottayam: { overall: 58, flood: 78, landslide: 32, drought: 15, rainfall: 72 },
  kozhikode: { overall: 54, flood: 62, landslide: 55, drought: 20, rainfall: 74 },
  malappuram: { overall: 52, flood: 58, landslide: 50, drought: 25, rainfall: 66 },
  kannur: { overall: 45, flood: 52, landslide: 35, drought: 20, rainfall: 68 },
  kasaragod: { overall: 42, flood: 48, landslide: 25, drought: 35, rainfall: 62 },
  palakkad: { overall: 50, flood: 38, landslide: 22, drought: 75, rainfall: 45 },
  kollam: { overall: 46, flood: 55, landslide: 25, drought: 22, rainfall: 60 },
  thiruvananthapuram: { overall: 45, flood: 52, landslide: 25, drought: 25, rainfall: 58 },
};

export function getDistrictLayerScore(districtName, layer) {
  const key = normalizeDistrictName(districtName);
  const profile = DISTRICT_HAZARD_SCORES[key] || {
    overall: 45, flood: 45, landslide: 45, drought: 45, rainfall: 45,
  };
  switch (layer) {
    case "Flood": return profile.flood;
    case "Landslide": return profile.landslide;
    case "Drought": return profile.drought;
    case "Rainfall": return profile.rainfall;
    default: return profile.overall;
  }
}
