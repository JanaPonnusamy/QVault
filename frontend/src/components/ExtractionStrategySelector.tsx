import { useEffect, useRef, useState } from "react";

import { api } from "../api/client";
import type { EstimateResponse, ExtractionOptions, FrameExtractionStrategy, SamplingFps } from "../types";

const INTERVALS = [0.25, 0.5, 1, 2, 5];
const MAX_FRAMES_OPTIONS: { label: string; value: number | null }[] = [
  { label: "Auto", value: null },
  { label: "25", value: 25 },
  { label: "50", value: 50 },
  { label: "100", value: 100 },
  { label: "200", value: 200 },
  { label: "Unlimited", value: 0 },
];

const SAMPLING_OPTIONS: { label: string; value: SamplingFps }[] = [
  { label: "Every decoded frame (highest quality)", value: null },
  { label: "30 FPS", value: 30 },
  { label: "15 FPS", value: 15 },
  { label: "10 FPS (default)", value: 10 },
  { label: "5 FPS", value: 5 },
  { label: "2 FPS", value: 2 },
  { label: "1 FPS", value: 1 },
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
  url,
  estimateEndpoint,
}: {
  value: ExtractionOptions;
  onChange: (next: ExtractionOptions) => void;
  disabled?: boolean;
  /** Current URL being submitted -- used to fetch the pre-processing frame-count estimate. */
  url: string;
  /** e.g. "/api/extractor/estimate" or "/api/sources/instagram/estimate" */
  estimateEndpoint: string;
}) {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [estimate, setEstimate] = useState<EstimateResponse | null>(null);
  const [estimating, setEstimating] = useState(false);
  const debounceRef = useRef<number | null>(null);

  function set<K extends keyof ExtractionOptions>(key: K, val: ExtractionOptions[K]) {
    onChange({ ...value, [key]: val });
  }

  useEffect(() => {
    setEstimate(null);
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    if (!advancedOpen || !url.trim()) return;

    debounceRef.current = window.setTimeout(async () => {
      setEstimating(true);
      try {
        const res = await api.post<EstimateResponse>(estimateEndpoint, {
          url,
          sampling_fps: value.sampling_fps,
        });
        setEstimate(res.data);
      } catch {
        setEstimate(null);
      } finally {
        setEstimating(false);
      }
    }, 600);

    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
    };
  }, [url, value.sampling_fps, advancedOpen, estimateEndpoint]);

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
          <label className="form-label small fw-medium mb-1">Frame Sampling Mode</label>
          <select
            className="form-select form-select-sm mb-1"
            disabled={disabled}
            value={value.sampling_fps === null ? "every" : value.sampling_fps}
            onChange={(e) => {
              const raw = e.target.value;
              set("sampling_fps", raw === "every" ? null : (parseInt(raw, 10) as SamplingFps));
            }}
          >
            {SAMPLING_OPTIONS.map((o) => (
              <option key={o.label} value={o.value === null ? "every" : o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <div className="small text-muted mb-2" style={{ fontSize: "0.72rem" }}>
            Sampling determines how many frames are examined; the strategy above
            determines which of those are kept.
          </div>
          <div className="small mb-2">
            {estimating && <span className="text-muted">Estimating frame count...</span>}
            {!estimating && estimate && (
              <span className="text-muted">
                <i className="bi bi-info-circle me-1" />
                ~{estimate.estimated_frames} frames will be examined (~{estimate.duration.toFixed(1)}s
                {" "}&times; {estimate.fps} fps)
              </span>
            )}
            {!estimating && !estimate && url.trim() && (
              <span className="text-muted">Enter a URL above to see an estimate.</span>
            )}
          </div>

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
