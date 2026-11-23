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
  { key: "low", label: "Low index", min: 0, range: "0–39", color: "#55a896", ink: "#1b5a4d", tint: "#e0f1ed" },
  { key: "moderate", label: "Moderate index", min: 40, range: "40–59", color: "#e8c24a", ink: "#6b5206", tint: "#fbf1cc" },
  { key: "high", label: "Elevated index", min: 60, range: "60–74", color: "#e7843b", ink: "#86390a", tint: "#fbe3cf" },
  { key: "severe", label: "Very high index", min: 75, range: "75–100", color: "#b3282a", ink: "#7a1517", tint: "#f6d8d6" },
];

// Where one band ends and the next begins (drawn as ticks on the meters).
export const BAND_THRESHOLDS = RISK_BANDS.slice(1).map((b) => b.min);

export function getRiskBand(score) {
  if (score === null || score === undefined || score === "" || Number.isNaN(Number(score))) return null;
  const n = Number(score);
  const bands = RISK_BANDS;
  let found = bands[0];
  for (const band of bands) {
    if (n >= band.min) found = band;
  }
  return found;
}

export function getDistrictLayerScore(districtName, layer, riskByDistrict = {}) {
  const key = normalizeDistrictName(districtName);
  const live = riskByDistrict?.[key];
  const index = live?.preparedness_index;
  switch (layer) {
    case "Flood": return live?.hazards?.flood?.score ?? live?.flood_risk ?? null;
    case "Landslide": return live?.hazards?.landslide?.score ?? live?.landslide_risk ?? null;
    case "Drought": return live?.hazards?.drought?.score ?? live?.drought_risk ?? null;
    default: return index?.score ?? live?.composite_score ?? live?.overall_risk ?? null;
  }
}

export function getDistrictLayerConfidenceScore(districtName, layer, riskByDistrict = {}) {
  const live = riskByDistrict?.[normalizeDistrictName(districtName)];
  if (!live) return null;
  const hazardKey = layer === "Flood" ? "flood" : layer === "Landslide" ? "landslide" : layer === "Drought" ? "drought" : null;
  if (hazardKey) return live?.hazards?.[hazardKey]?.confidence_score ?? null;
  return live?.preparedness_index?.confidence_score ?? live?.uncertainty?.confidence_score ?? null;
}

export function getDistrictLayerProvenance(layer, riskByDistrict = {}) {
  const hasVerifiedModel = Object.values(riskByDistrict).some((item) =>
    item?.status === "OK" && ["VERIFIED_HISTORICAL", "PROXY_CALIBRATED"].includes(item?.model_provenance || item?.metadata?.model_provenance)
  );
  if (hasVerifiedModel) return "MODEL_OUTPUT";
  const hasExperimental = Object.values(riskByDistrict).some((item) =>
    item?.status === "EXPERIMENTAL_INDEX" || item?.score_semantics === "EXPERIMENTAL_INDEX_NOT_PROBABILITY"
  );
  return hasExperimental ? "EXPERIMENTAL_INDEX" : "NO_DATA";
}
