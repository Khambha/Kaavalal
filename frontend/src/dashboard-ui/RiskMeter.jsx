import { BAND_THRESHOLDS, getRiskBand } from "./riskScale";

export default function RiskMeter({ label, value, featured = false }) {
  const available = value !== null && value !== undefined;
  const band = available ? getRiskBand(value) : null;
  const pct = available ? Math.min(Math.max(Number(value), 0), 100) : 0;

  return (
    <div className={`meter${featured ? " is-featured" : ""}`}>
      <div className="meter-head">
        <span className="meter-label">{label}</span>
        <span className="meter-read">
          {band ? (
            <span className="band-chip" style={{ background: band.tint, color: band.ink }}>
              {band.label}
            </span>
          ) : (
            <span className="band-chip is-none">Unavailable</span>
          )}
          <strong className="meter-num">{available ? `${pct}%` : "—"}</strong>
        </span>
      </div>
      <div
        className="meter-track"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={available ? pct : undefined}
        aria-valuetext={available ? `${pct}%, ${band.label}` : "Unavailable"}
      >
        <span className="meter-fill" style={{ width: `${pct}%`, background: band?.color }} />
        {BAND_THRESHOLDS.map((t) => (
          <i className="meter-tick" key={t} style={{ left: `${t}%` }} />
        ))}
      </div>
    </div>
  );
}
