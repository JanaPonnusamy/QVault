import { useState } from "react";

import type { ExtractionOptions, FrameExtractionStrategy } from "../types";

const INTERVALS = [0.25, 0.5, 1, 2, 5];
const MAX_FRAMES_OPTIONS: { label: string; value: number | null }[] = [
  { label: "Auto", value: null },
  { label: "25", value: 25 },
  { label: "50", value: 50 },
  { label: "100", value: 100 },
  { label: "200", value: 200 },
  { label: "Unlimited", value: 0 },
];

const STRATEGIES: { value: FrameExtractionStrategy; label: string; description: string }[] = [
  { value: "fixed_interval", label: "Fixed Interval", description: "Sample every N seconds." },
  { value: "scene_detection", label: "Scene Detection", description: "Extract when the visual scene changes (new slide, camera cut)." },
  { value: "ocr_text_change", label: "OCR Text Change", description: "Sample, OCR, and keep only frames whose text changed." },
  { value: "hybrid", label: "Hybrid (Recommended)", description: "Scene detection + OCR text-diff + quality filtering." },
];

export default function ExtractionStrategySelector({
  value,
  onChange,
  disabled,
}: {
  value: ExtractionOptions;
  onChange: (next: ExtractionOptions) => void;
  disabled?: boolean;
}) {
  const [advancedOpen, setAdvancedOpen] = useState(false);

  function set<K extends keyof ExtractionOptions>(key: K, val: ExtractionOptions[K]) {
    onChange({ ...value, [key]: val });
  }

  return (
    <div className="mt-2">
      <div className="small fw-medium text-muted mb-1">Frame Extraction Strategy</div>
      {STRATEGIES.map((s) => (
        <div key={s.value} className="form-check mb-1">
          <input
            className="form-check-input"
            type="radio"
            name="extraction-strategy"
            id={`strategy-${s.value}`}
            checked={value.strategy === s.value}
            disabled={disabled}
            onChange={() => set("strategy", s.value)}
          />
          <label className="form-check-label small" htmlFor={`strategy-${s.value}`}>
            {s.label}
            <span className="text-muted d-block" style={{ fontSize: "0.72rem" }}>
              {s.description}
            </span>
          </label>
          {s.value === "fixed_interval" && value.strategy === "fixed_interval" && (
            <select
              className="form-select form-select-sm mt-1"
              style={{ maxWidth: 160 }}
              disabled={disabled}
              value={value.interval ?? 2}
              onChange={(e) => set("interval", parseFloat(e.target.value))}
            >
              {INTERVALS.map((i) => (
                <option key={i} value={i}>
                  {i} sec
                </option>
              ))}
            </select>
          )}
        </div>
      ))}

      <button
        type="button"
        className="btn btn-link btn-sm px-0 mt-1"
        onClick={() => setAdvancedOpen((v) => !v)}
      >
        <i className={`bi bi-chevron-${advancedOpen ? "down" : "right"} me-1`} />
        Advanced
      </button>

      {advancedOpen && (
        <div className="border rounded p-2 mt-1">
          <label className="form-label small fw-medium mb-1">Maximum Frames</label>
          <select
            className="form-select form-select-sm mb-2"
            disabled={disabled}
            value={value.max_frames === null ? "auto" : value.max_frames}
            onChange={(e) => {
              const raw = e.target.value;
              set("max_frames", raw === "auto" ? null : parseInt(raw, 10));
            }}
          >
            {MAX_FRAMES_OPTIONS.map((o) => (
              <option key={o.label} value={o.value === null ? "auto" : o.value}>
                {o.label}
              </option>
            ))}
          </select>

          {[
            { key: "remove_duplicates" as const, label: "Remove duplicate frames" },
            { key: "keep_best_quality" as const, label: "Keep highest quality frame" },
            { key: "ignore_blank" as const, label: "Ignore blank frames" },
            { key: "ignore_blurred" as const, label: "Ignore blurred frames" },
          ].map((c) => (
            <div className="form-check" key={c.key}>
              <input
                className="form-check-input"
                type="checkbox"
                id={`opt-${c.key}`}
                disabled={disabled}
                checked={value[c.key]}
                onChange={(e) => set(c.key, e.target.checked)}
              />
              <label className="form-check-label small" htmlFor={`opt-${c.key}`}>
                {c.label}
              </label>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
