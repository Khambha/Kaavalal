import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  MapContainer,
  TileLayer,
  GeoJSON,
  CircleMarker,
  Marker,
  Pane,
  Popup,
  Tooltip,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

import lacData from "./lac_locations.json";
import {
  RISK_BANDS,
  getDistrictLayerScore,
  getRiskBand,
  normalizeDistrictName,
} from "./riskScale";

const INK = "#0f2a33";
const shelterMapIcon = L.divIcon({
  className: "shelter-map-div-icon",
  html: '<span class="shelter-map-glyph" aria-hidden="true"><svg viewBox="0 0 24 24" focusable="false"><path d="M3.5 10.5 12 4l8.5 6.5M6 9.5V20h12V9.5M10 20v-6h4v6" /></svg></span>',
  iconSize: [34, 40],
  iconAnchor: [17, 38],
  popupAnchor: [0, -34],
});

function getFeatureDistrictName(feature) {
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

const cleanDistrictName = (name) => String(name || "").replace(/\bdistrict\b/i, "").trim();
const hasCoordinates = (item) => item.latitude != null && item.longitude != null && item.latitude !== "" && item.longitude !== "" && Number.isFinite(Number(item.latitude)) && Number.isFinite(Number(item.longitude));

// Camera controller: whole state on first load, then district / constituency focus.
function MapBoundsController({ geojson, selectedDistrict, selectedLac }) {
  const map = useMap();
  const prevDistrictRef = useRef(null);
  const prevLacRef = useRef(null);
  const initialFitDone = useRef(false);

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

    // A constituency is selected: centre on it.
    if (selectedLac?.latitude && selectedLac?.longitude) {
      prevDistrictRef.current = distKey;
      prevLacRef.current = lacKey;
      if (lacChanged) {
        const lat = Number(selectedLac.latitude);
        const lng = Number(selectedLac.longitude);
        if (Number.isFinite(lat) && Number.isFinite(lng)) {
          const targetZoom = Math.min(Math.max(map.getZoom(), 10.25), 11);
          map.setView([lat, lng], targetZoom, { animate: true, duration: 0.45 });
        }
      }
      return;
    }

    // Boundaries not loaded yet: leave the change pending so it is applied on arrival.
    if (!geojson?.features?.length) return;

    prevDistrictRef.current = distKey;
    prevLacRef.current = lacKey;

    const fitAll = (animate) => {
      const allBounds = L.geoJSON(geojson).getBounds();
      if (allBounds.isValid()) {
        map.fitBounds(allBounds, { padding: [8, 8], maxZoom: 8, animate, duration: 0.5 });
      }
    };

    // On first paint, focus a selected district (or constituency above) when
    // the dashboard has a signed-in user's saved area.
    if (!initialFitDone.current) {
      initialFitDone.current = true;
      if (!selectedDistrict || selectedDistrict === "ALL") {
        fitAll(false);
        return;
      }
    }

    if (!selectedDistrict || selectedDistrict === "ALL") {
      if (districtChanged || lacChanged) fitAll(true);
      return;
    }

    if (districtChanged || lacChanged) {
      const selectedNorm = normalizeDistrictName(distKey);
      const matching = geojson.features.filter(
        (f) => normalizeDistrictName(getFeatureDistrictName(f)) === selectedNorm
      );
      if (matching.length > 0) {
        const bounds = L.geoJSON({ type: "FeatureCollection", features: matching }).getBounds();
        if (bounds.isValid()) {
          map.fitBounds(bounds, { padding: [24, 24], maxZoom: 9.8, animate: true, duration: 0.5 });
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
  shelters = [],
  showShelters = true,
  helpRequests = [],
  showHelpRequests = false,
  onClaimHelpRequest,
}) {
  const [keralaGeoJSON, setKeralaGeoJSON] = useState(null);
  const [loadingMap, setLoadingMap] = useState(true);
  const [mapError, setMapError] = useState("");

  useEffect(() => {
    let cancelled = false;

    fetch("/Data/Kerala_districts.geojson")
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to load Kerala GeoJSON`);
        return res.json();
      })
      .then((data) => {
        if (!cancelled && data && data.features) setKeralaGeoJSON(data);
      })
      .catch((err) => {
        if (!cancelled) {
          console.error("GeoJSON load error:", err);
          setMapError("Couldn't load district boundaries. Check that /Data/Kerala_districts.geojson is being served.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingMap(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const allConstituencies = useMemo(() => {
    return (lacData.constituencies || []).filter((lac) => {
      const lat = Number(lac.latitude);
      const lng = Number(lac.longitude);
      return (
        Number.isFinite(lat) && Number.isFinite(lng) &&
        lat >= 8.0 && lat <= 13.0 && lng >= 74.0 && lng <= 78.0
      );
    });
  }, []);

  const visibleConstituencies = useMemo(() => {
    if (!showConstituencies) return [];

    if (Array.isArray(lacs) && lacs.length > 0) {
      return lacs
        .filter((lac) => Number.isFinite(Number(lac.latitude)) && Number.isFinite(Number(lac.longitude)))
        .map((lac) => ({
          lac_code: String(lac.administrative_code || lac.code || lac.id),
          lac_name: lac.name,
          district:
            lac.district ||
            (typeof selectedDistrict === "object" ? selectedDistrict?.name : selectedDistrict) ||
            "",
          latitude: Number(lac.latitude),
          longitude: Number(lac.longitude),
          raw: lac,
        }));
    }

    if (!selectedDistrict || selectedDistrict === "ALL") return allConstituencies;

    const distName = typeof selectedDistrict === "string" ? selectedDistrict : selectedDistrict.name;
    const targetNorm = normalizeDistrictName(distName);
    return allConstituencies.filter((lac) => normalizeDistrictName(lac.district) === targetNorm);
  }, [allConstituencies, selectedDistrict, showConstituencies, lacs]);

  // One label per district, placed at the centre of its bounds.
  const districtLabels = useMemo(() => {
    if (!keralaGeoJSON) return [];
    return keralaGeoJSON.features.map((feature) => {
      const c = L.geoJSON(feature).getBounds().getCenter();
      const name = cleanDistrictName(getFeatureDistrictName(feature));
      return {
        name,
        position: [c.lat, c.lng],
        icon: L.divIcon({
          className: "district-label",
          html: `<span>${name}</span>`,
          iconSize: [0, 0],
        }),
      };
    });
  }, [keralaGeoJSON]);

  const handleDistrictClick = (feature) => {
    const rawName = getFeatureDistrictName(feature);
    const norm = normalizeDistrictName(rawName);
    const match = districts.find((d) => normalizeDistrictName(d.name) === norm);
    onSelectDistrict(match || { id: null, name: cleanDistrictName(rawName) });
    if (onSelectLac) onSelectLac(null);
  };

  const currentDistName =
    selectedDistrict && typeof selectedDistrict === "object"
      ? selectedDistrict.name
      : selectedDistrict;
  const hasDistrictSelected = currentDistName && currentDistName !== "ALL";

  const districtStyle = (feature) => {
    const distName = getFeatureDistrictName(feature);
    const isSelected =
      hasDistrictSelected &&
      normalizeDistrictName(currentDistName) === normalizeDistrictName(distName);
    const band = getRiskBand(getDistrictLayerScore(distName, selectedLayer));

    // The risk colour is always kept; selection is shown by outline and emphasis.
    return {
      fillColor: band.color,
      weight: isSelected ? 3 : 1.2,
      opacity: 1,
      color: isSelected ? INK : "#ffffff",
      fillOpacity: isSelected ? 0.92 : hasDistrictSelected ? 0.62 : 0.78,
    };
  };

  const lacMatches = (lac) =>
    selectedLac &&
    (String(selectedLac.administrative_code || "").trim() === String(lac.lac_code || "").trim() ||
      String(selectedLac.code || "").trim() === String(lac.lac_code || "").trim() ||
      String(selectedLac.id || "").trim() === String(lac.lac_code || "").trim() ||
      selectedLac.name?.toLowerCase() === lac.lac_name?.toLowerCase());

  const toLacObject = (lac) =>
    lac.raw || {
      id: lac.id || Number(lac.lac_code),
      name: lac.lac_name,
      administrative_code: lac.lac_code,
      district: lac.district,
      latitude: lac.latitude,
      longitude: lac.longitude,
    };

  return (
    <div className="map-framed-canvas">
      {loadingMap && (
        <div className="map-overlay" role="status">
          <div className="map-spinner" />
          <span>Loading district boundaries…</span>
        </div>
      )}

      {mapError && (
        <div className="map-overlay is-error" role="alert">
          <span>{mapError}</span>
        </div>
      )}

      <MapContainer
        center={[10.5, 76.2]}
        zoom={7.5}
        zoomSnap={0.25}
        minZoom={6}
        maxZoom={13}
        scrollWheelZoom={true}
        className="kerala-leaflet-container"
        zoomControl={true}
      >
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

        {keralaGeoJSON && (
          <GeoJSON
            key={`districts-${selectedLayer}-${selectedDistrict?.id || selectedDistrict}`}
            data={keralaGeoJSON}
            style={districtStyle}
            onEachFeature={(feature, layer) => {
              const distName = getFeatureDistrictName(feature);
              const score = getDistrictLayerScore(distName, selectedLayer);
              const band = getRiskBand(score);

              layer.bindTooltip(
                `<div class="leaflet-custom-tooltip">
                  <strong>${cleanDistrictName(distName)}</strong>
                  <span>${selectedLayer} ${score}% · ${band.label}</span>
                 </div>`,
                { sticky: true, opacity: 1 }
              );

              layer.on({
                mouseover: (e) => {
                  e.target.setStyle({ weight: 2.6, fillOpacity: 0.95, color: INK });
                },
                mouseout: (e) => e.target.setStyle(districtStyle(feature)),
                click: () => handleDistrictClick(feature),
              });
            }}
          />
        )}

        {!selectedLac &&
          districtLabels.map((label) => (
            <Marker
              key={label.name}
              position={label.position}
              icon={label.icon}
              interactive={false}
              keyboard={false}
            />
          ))}

        {/* Place LAC and shelter hit targets above district polygons. District hover
            styling must never raise a polygon over these clickable map points. */}
        <Pane name="citizenPopups" style={{ zIndex: 800, pointerEvents: "none" }} />
        <Pane name="citizenMapPoints" style={{ zIndex: 610, pointerEvents: "auto" }}>
        {visibleConstituencies.map((lac) => {
          const isLacSelected = lacMatches(lac);
          const center = [Number(lac.latitude), Number(lac.longitude)];

          return (
            <React.Fragment key={`${lac.lac_code}_${lac.lac_name}`}>
              {isLacSelected && (
                <CircleMarker
                  center={center}
                  radius={13}
                  pane="citizenMapPoints"
                  pathOptions={{ color: INK, weight: 1.5, fillColor: INK, fillOpacity: 0.12 }}
                  interactive={false}
                />
              )}

              <CircleMarker
                center={center}
                radius={isLacSelected ? 7 : 4.5}
                pane="citizenMapPoints"
                interactive={true}
                pathOptions={{
                  color: "#ffffff",
                  weight: isLacSelected ? 2.5 : 1.5,
                  fillColor: INK,
                  fillOpacity: 1,
                }}
                eventHandlers={{ click: () => onSelectLac && onSelectLac(toLacObject(lac)) }}
              >
                <Tooltip direction="top" offset={[0, -5]}>
                  <span>{lac.lac_name} (LAC {lac.lac_code})</span>
                </Tooltip>

                <Popup pane="citizenPopups" offset={[0, -16]}>
                  <div className="lac-marker-popup">
                    <span className="popup-badge">Constituency</span>
                    <h4>{lac.lac_name}</h4>
                    <div className="popup-row">
                      <span>LAC code</span> <strong>{lac.lac_code}</strong>
                    </div>
                    <div className="popup-row">
                      <span>District</span> <strong>{lac.district}</strong>
                    </div>
                    <div className="popup-row">
                      <span>Coordinates</span>
                      <strong>{Number(lac.latitude).toFixed(3)}, {Number(lac.longitude).toFixed(3)}</strong>
                    </div>
                    <button
                      type="button"
                      className="popup-select-btn"
                      onClick={() => onSelectLac && onSelectLac(toLacObject(lac))}
                    >
                      Select constituency
                    </button>
                  </div>
                </Popup>
              </CircleMarker>
            </React.Fragment>
          );
        })}

        </Pane>
        <Pane name="shelterMarkers" style={{ zIndex: 630, pointerEvents: "auto" }}>
        {showShelters && shelters.filter(s => Number.isFinite(Number(s.latitude)) && Number.isFinite(Number(s.longitude))).map(shelter => (
          <Marker key={`shelter-${shelter.id}`} position={[Number(shelter.latitude), Number(shelter.longitude)]} pane="shelterMarkers" icon={shelterMapIcon} title={shelter.name}>
            <Tooltip direction="top" offset={[0, -5]}>{shelter.name} · {shelter.available} spaces</Tooltip>
            <Popup pane="citizenPopups"><div className="lac-marker-popup"><span className="popup-badge shelter-popup-badge">Emergency shelter</span><h4>{shelter.name}</h4><div className="popup-row"><span>Building</span><strong>{shelter.building_type}</strong></div><div className="popup-row"><span>Area</span><strong>{shelter.lac}, {shelter.district}</strong></div><div className="popup-row"><span>Address</span><strong>{shelter.address}</strong></div><div className="popup-row"><span>Capacity</span><strong>{shelter.occupied}/{shelter.capacity}</strong></div></div></Popup>
          </Marker>
        ))}
        </Pane>
        <Pane name="helpRequestMarkers" style={{ zIndex: 640, pointerEvents: "auto" }}>
        {showHelpRequests && helpRequests
          .filter(hasCoordinates)
          .filter(item => !["Resolved", "Rejected"].includes(item.status))
          .map(item => <CircleMarker
            key={`help-request-${item.id}`}
            center={[Number(item.latitude), Number(item.longitude)]}
            radius={5}
            pane="helpRequestMarkers"
            pathOptions={{ color: "#ffffff", weight: 1.5, fillColor: "#d34438", fillOpacity: 0.95 }}
          >
            <Tooltip direction="top" offset={[0, -5]}>Request #{item.id} · {item.urgency}</Tooltip>
            <Popup pane="citizenPopups" offset={[0, -5]}>
              <div className="lac-marker-popup">
                <span className="popup-badge people-popup-badge">Citizen request · {item.urgency}</span>
                <h4>{item.emergency_type}</h4>
                <div className="popup-row"><span>People affected</span><strong>{item.people_affected}</strong></div>
                <div className="popup-row"><span>Status</span><strong>{item.status}</strong></div>
                <div className="popup-row"><span>Area</span><strong>{item.lac}, {item.district}</strong></div>
                <p className="people-popup-description">{item.situation_description}</p>
                {!item.assigned_responder_id
                  ? <button type="button" className="popup-select-btn" onClick={() => onClaimHelpRequest?.(item)}>Claim request</button>
                  : <div className="popup-row"><span>Assignment</span><strong>Claimed by responder</strong></div>}
              </div>
            </Popup>
          </CircleMarker>)}
        </Pane>
      </MapContainer>

      {/* Legend: bottom-left so it never collides with the Leaflet attribution */}
      <div className="map-legend">
        <div className="legend-head">
          <span className="legend-title">{selectedLayer}</span>
          <span className="legend-tag" title="District scores on the map are placeholder values, not official measurements.">
            Sample scores
          </span>
        </div>
        <ul className="legend-list">
          {RISK_BANDS.map((band) => (
            <li key={band.key}>
              <span className="legend-swatch" style={{ background: band.color }} />
              <span className="legend-name">{band.label}</span>
              <span className="legend-range">{band.range}</span>
            </li>
          ))}
          {showConstituencies && (
            <li className="legend-pin-row">
              <span className="legend-pin" />
              <span className="legend-name">Constituency</span>
            </li>
          )}
          {showShelters && shelters.length > 0 && <li className="legend-pin-row"><span className="legend-pin shelter-pin" /><span className="legend-name">Shelter</span></li>}
          {showHelpRequests && <li className="legend-pin-row"><span className="legend-pin people-pin" /><span className="legend-name">Active citizen request</span></li>}
        </ul>
      </div>
    </div>
  );
}
