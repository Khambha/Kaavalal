import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  MapContainer,
  TileLayer,
  GeoJSON,
  CircleMarker,
  Popup,
  Tooltip,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

import lacData from "./lac_locations.json";

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

export function getFeatureDistrictName(feature) {
  const props = feature?.properties || {};
  return (
    props.name ||
    props.DISTRICT ||
    props.district ||
    props.NAME_2 ||
    props.alt_name ||
    ""
  );
}

// Sophisticated, harmonious hazard scores per district
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

function getDistrictLayerScore(districtName, layer) {
  const key = normalizeDistrictName(districtName);
  const profile = DISTRICT_HAZARD_SCORES[key] || {
    overall: 45,
    flood: 45,
    landslide: 45,
    drought: 45,
    rainfall: 45,
  };

  switch (layer) {
    case "Flood":
      return profile.flood;
    case "Landslide":
      return profile.landslide;
    case "Drought":
      return profile.drought;
    case "Rainfall":
      return profile.rainfall;
    case "Overall Risk":
    default:
      return profile.overall;
  }
}

// Curated pastel/intelligence color palette (matching Image 1)
function getLayerColor(score, isSelected) {
  if (isSelected) {
    return "#5ea396"; // Highlighted active teal
  }

  if (score >= 75) return "#d97d54"; // High - terracotta coral
  if (score >= 60) return "#e59e67"; // Moderate-high - warm amber
  if (score >= 45) return "#7ebaa9"; // Moderate - sage teal
  return "#9bcbc1"; // Low - serene pastel teal
}

// Professional, buttery-smooth map camera controller
function MapBoundsController({ geojson, selectedDistrict, selectedLac }) {
  const map = useMap();
  const prevDistrictRef = useRef(null);
  const prevLacRef = useRef(null);

  useEffect(() => {
    const distKey =
      selectedDistrict && typeof selectedDistrict === "object"
        ? selectedDistrict.name
        : selectedDistrict;
    const lacKey = selectedLac
      ? `${selectedLac.administrative_code || selectedLac.code || selectedLac.id}_${selectedLac.latitude}_${selectedLac.longitude}`
      : null;

    const districtChanged = prevDistrictRef.current !== distKey;
    const lacChanged = prevLacRef.current !== lacKey;

    prevDistrictRef.current = distKey;
    prevLacRef.current = lacKey;

    // Case 1: Specific LAC selected -> Direct smooth focus without wild parabolic swoop
    if (selectedLac?.latitude && selectedLac?.longitude) {
      if (lacChanged) {
        const lat = Number(selectedLac.latitude);
        const lng = Number(selectedLac.longitude);
        if (Number.isFinite(lat) && Number.isFinite(lng)) {
          // Direct smooth view translation - preserves district visual context
          const targetZoom = Math.min(Math.max(map.getZoom(), 10.2), 11);
          map.setView([lat, lng], targetZoom, {
            animate: true,
            duration: 0.45,
          });
        }
      }
      return;
    }

    // Case 2: LAC was cleared or District changed -> Pan smoothly to district or whole Kerala
    if (!geojson?.features?.length) return;

    if (!selectedDistrict || selectedDistrict === "ALL") {
      if (districtChanged || lacChanged) {
        const allBounds = L.geoJSON(geojson).getBounds();
        if (allBounds.isValid()) {
          map.fitBounds(allBounds, {
            padding: [20, 20],
            maxZoom: 8,
            animate: true,
            duration: 0.5,
          });
        }
      }
      return;
    }

    if (districtChanged || lacChanged) {
      const selectedNorm = normalizeDistrictName(distKey);
      const matchingFeatures = geojson.features.filter(
        (feature) => normalizeDistrictName(getFeatureDistrictName(feature)) === selectedNorm
      );

      if (matchingFeatures.length > 0) {
        const bounds = L.geoJSON({
          type: "FeatureCollection",
          features: matchingFeatures,
        }).getBounds();

        if (bounds.isValid()) {
          map.fitBounds(bounds, {
            padding: [24, 24],
            maxZoom: 9.8,
            animate: true,
            duration: 0.5,
          });
        }
      }
    }
  }, [geojson, selectedDistrict, selectedLac, map]);

  return null;
}

export default function KeralaMap({
  selectedDistrict,
  onSelectDistrict,
  selectedLac,
  onSelectLac,
  districts = [],
  selectedLayer = "Overall Risk",
  showConstituencies = true,
  lacs = [],
}) {
  const [keralaGeoJSON, setKeralaGeoJSON] = useState(null);
  const [loadingMap, setLoadingMap] = useState(true);
  const [mapError, setMapError] = useState("");

  // Load Kerala District Boundaries GeoJSON
  useEffect(() => {
    let cancelled = false;
    setLoadingMap(true);

    fetch("/Data/Kerala_districts.geojson")
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to load Kerala GeoJSON`);
        return res.json();
      })
      .then((data) => {
        if (!cancelled && data && data.features) {
          setKeralaGeoJSON(data);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          console.error("GeoJSON load error:", err);
          setMapError("Could not load district boundaries.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingMap(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  // Parse Assembly Constituencies from lac_locations.json
  const allConstituencies = useMemo(() => {
    return (lacData.constituencies || []).filter((lac) => {
      const lat = Number(lac.latitude);
      const lng = Number(lac.longitude);
      return (
        Number.isFinite(lat) &&
        Number.isFinite(lng) &&
        lat >= 8.0 &&
        lat <= 13.0 &&
        lng >= 74.0 &&
        lng <= 78.0
      );
    });
  }, []);

  // Filter constituencies for selected district
  const visibleConstituencies = useMemo(() => {
    if (!showConstituencies) return [];

    if (Array.isArray(lacs) && lacs.length > 0) {
      return lacs
        .filter((lac) => {
          const lat = Number(lac.latitude);
          const lng = Number(lac.longitude);
          return Number.isFinite(lat) && Number.isFinite(lng);
        })
        .map((lac) => ({
          lac_code: String(lac.administrative_code || lac.code || lac.id),
          lac_name: lac.name,
          district: lac.district || (typeof selectedDistrict === "object" ? selectedDistrict?.name : selectedDistrict) || "",
          latitude: Number(lac.latitude),
          longitude: Number(lac.longitude),
          raw: lac,
        }));
    }

    if (!selectedDistrict || selectedDistrict === "ALL") {
      return allConstituencies;
    }

    const distName = typeof selectedDistrict === "string" ? selectedDistrict : selectedDistrict.name;
    const targetNorm = normalizeDistrictName(distName);

    return allConstituencies.filter(
      (lac) => normalizeDistrictName(lac.district) === targetNorm
    );
  }, [allConstituencies, selectedDistrict, showConstituencies, lacs]);

  // Click handler on district polygon
  const handleDistrictClick = (feature) => {
    const rawName = getFeatureDistrictName(feature);
    const norm = normalizeDistrictName(rawName);

    const match = districts.find(
      (d) => normalizeDistrictName(d.name) === norm
    );

    if (match) {
      onSelectDistrict(match);
    } else {
      onSelectDistrict({ id: null, name: rawName.replace(/\bdistrict\b/i, "").trim() });
    }

    if (onSelectLac) {
      onSelectLac(null);
    }
  };

  // Polygon styling
  const districtStyle = (feature) => {
    const distName = getFeatureDistrictName(feature);
    const norm = normalizeDistrictName(distName);

    const currentDistName =
      selectedDistrict && typeof selectedDistrict === "object"
        ? selectedDistrict.name
        : selectedDistrict;

    const isSelected =
      currentDistName &&
      currentDistName !== "ALL" &&
      normalizeDistrictName(currentDistName) === norm;

    const score = getDistrictLayerScore(distName, selectedLayer);
    const fillColor = getLayerColor(score, isSelected);

    return {
      fillColor: fillColor,
      weight: isSelected ? 2.5 : 1.2,
      opacity: 1,
      color: isSelected ? "#174f5d" : "#ffffff",
      fillOpacity: isSelected ? 0.88 : 0.72,
    };
  };

  return (
    <div className="map-framed-canvas">
      {loadingMap && (
        <div className="map-loading-overlay">
          <div className="map-spinner" />
          <span>Rendering Kerala boundaries...</span>
        </div>
      )}

      {mapError && (
        <div className="map-error-overlay">
          <span>{mapError}</span>
        </div>
      )}

      <MapContainer
        center={[10.5, 76.2]}
        zoom={7.5}
        minZoom={6}
        maxZoom={13}
        scrollWheelZoom={true}
        className="kerala-leaflet-container"
        zoomControl={true}
      >
        {/* Esri World Light Gray Base: Clean, crisp, NO API KEY REQUIRED, ZERO WATERMARKS */}
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; Esri'
          url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}"
          maxZoom={16}
        />

        <MapBoundsController
          geojson={keralaGeoJSON}
          selectedDistrict={selectedDistrict}
          selectedLac={selectedLac}
        />

        {/* District Boundaries GeoJSON */}
        {keralaGeoJSON && (
          <GeoJSON
            key={`districts-${selectedLayer}-${selectedDistrict?.id || selectedDistrict}`}
            data={keralaGeoJSON}
            style={districtStyle}
            onEachFeature={(feature, layer) => {
              const distName = getFeatureDistrictName(feature);
              const cleanName = distName.replace(/\bdistrict\b/i, "").trim();
              const score = getDistrictLayerScore(distName, selectedLayer);

              layer.bindTooltip(
                `<div class="leaflet-custom-tooltip">
                  <strong>${cleanName}</strong>
                  <span>${selectedLayer}: ${score}%</span>
                 </div>`,
                { sticky: true, opacity: 0.95 }
              );

              layer.on({
                mouseover: (e) => {
                  const l = e.target;
                  l.setStyle({
                    weight: 2.8,
                    fillOpacity: 0.92,
                    color: "#174f5d",
                  });
                  l.bringToFront();
                },
                mouseout: (e) => {
                  e.target.setStyle(districtStyle(feature));
                },
                click: () => {
                  handleDistrictClick(feature);
                },
              });
            }}
          />
        )}

        {/* Assembly Constituency (LAC) Markers */}
        {visibleConstituencies.map((lac) => {
          const lacCodeStr = String(lac.lac_code || "").trim();
          const isLacSelected =
            selectedLac &&
            (String(selectedLac.administrative_code || "").trim() === lacCodeStr ||
              String(selectedLac.code || "").trim() === lacCodeStr ||
              String(selectedLac.id || "").trim() === lacCodeStr ||
              selectedLac.name?.toLowerCase() === lac.lac_name?.toLowerCase());

          return (
            <React.Fragment key={`${lac.lac_code}_${lac.lac_name}`}>
              {/* Pulsing ring indicator for the selected LAC */}
              {isLacSelected && (
                <CircleMarker
                  center={[Number(lac.latitude), Number(lac.longitude)]}
                  radius={16}
                  pathOptions={{
                    color: "#0284c7",
                    weight: 2.2,
                    dashArray: "3, 3",
                    fillColor: "#38bdf8",
                    fillOpacity: 0.25,
                    className: "selected-lac-pulse",
                  }}
                  interactive={false}
                />
              )}

              {/* Main LAC CircleMarker */}
              <CircleMarker
                center={[Number(lac.latitude), Number(lac.longitude)]}
                radius={isLacSelected ? 7 : 4}
                pathOptions={{
                  color: isLacSelected ? "#0c4a6e" : "#ffffff",
                  weight: isLacSelected ? 2.5 : 1.2,
                  fillColor: isLacSelected ? "#0284c7" : "#dc2626",
                  fillOpacity: isLacSelected ? 1 : 0.85,
                }}
                eventHandlers={{
                  click: () => {
                    if (onSelectLac) {
                      onSelectLac(
                        lac.raw || {
                          id: lac.id || Number(lac.lac_code),
                          name: lac.lac_name,
                          administrative_code: lac.lac_code,
                          district: lac.district,
                          latitude: lac.latitude,
                          longitude: lac.longitude,
                        }
                      );
                    }
                  },
                }}
              >
                <Tooltip direction="top" offset={[0, -5]}>
                  <span>{lac.lac_name} (LAC {lac.lac_code})</span>
                </Tooltip>

                <Popup>
                  <div className="lac-marker-popup">
                    <span className="popup-badge">CONSTITUENCY</span>
                    <h4>{lac.lac_name}</h4>
                    <div className="popup-row">
                      <span>LAC Code:</span> <strong>{lac.lac_code}</strong>
                    </div>
                    <div className="popup-row">
                      <span>District:</span> <strong>{lac.district}</strong>
                    </div>
                    <div className="popup-row">
                      <span>Coordinates:</span>{" "}
                      <strong>
                        {Number(lac.latitude).toFixed(3)}, {Number(lac.longitude).toFixed(3)}
                      </strong>
                    </div>
                    <button
                      type="button"
                      className="popup-select-btn"
                      onClick={() => {
                        if (onSelectLac) {
                          onSelectLac({
                            id: lac.id || Number(lac.lac_code),
                            name: lac.lac_name,
                            administrative_code: lac.lac_code,
                            district: lac.district,
                            latitude: lac.latitude,
                            longitude: lac.longitude,
                          });
                        }
                      }}
                    >
                      Focus Constituency
                    </button>
                  </div>
                </Popup>
              </CircleMarker>
            </React.Fragment>
          );
        })}
      </MapContainer>

      {/* COMPACT MAP LEGEND */}
      <div className="map-compact-legend">
        <span className="legend-layer-title">{selectedLayer}</span>
        <div className="legend-items">
          <div className="legend-item">
            <span className="legend-swatch" style={{ background: "#9bcbc1" }} />
            <span>Low</span>
          </div>
          <div className="legend-item">
            <span className="legend-swatch" style={{ background: "#7ebaa9" }} />
            <span>Mod</span>
          </div>
          <div className="legend-item">
            <span className="legend-swatch" style={{ background: "#e59e67" }} />
            <span>High</span>
          </div>
          <div className="legend-item">
            <span className="legend-swatch" style={{ background: "#d97d54" }} />
            <span>Severe</span>
          </div>
          {showConstituencies && (
            <div className="legend-item">
              <span className="legend-lac-dot" />
              <span>LAC</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
