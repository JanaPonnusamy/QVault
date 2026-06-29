import type { Job } from "../types";

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-secondary",
  queued: "bg-secondary",
  downloading: "bg-info",
  scanning: "bg-info",
  extracting: "bg-warning text-dark",
  analyzing: "bg-primary",
  ready: "bg-success",
  completed: "bg-success",
  cancelled: "bg-dark",
  failed: "bg-danger",
};

export function StatusBadge({ status }: { status: string }) {
  return <span className={`badge ${STATUS_STYLES[status] ?? "bg-secondary"}`}>{status}</span>;
}

export default function JobProgress({ job }: { job: Job }) {
  const active = job.status !== "ready" && job.status !== "failed";
  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-1">
        <span className="fw-medium">
          <i className="bi bi-gear-wide-connected me-1" />
          {job.stage || job.status}
        </span>
        <StatusBadge status={job.status} />
      </div>
      <div className="progress" style={{ height: 8 }}>
        <div
          className={`progress-bar ${active ? "progress-bar-striped progress-bar-animated" : ""} ${
            job.status === "failed" ? "bg-danger" : ""
          }`}
          style={{ width: `${job.progress}%` }}
        />
      </div>
      {job.error && <div className="text-danger small mt-2">{job.error}</div>}
    </div>
  );
}
