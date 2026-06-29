export function confidenceClass(value: number): string {
  if (value >= 0.75) return "bg-success";
  if (value >= 0.5) return "bg-warning text-dark";
  return "bg-danger";
}

export default function ConfidenceBadge({
  value,
  label,
}: {
  value: number;
  label?: string;
}) {
  return (
    <span className={`badge ${confidenceClass(value)}`} title={label ? `${label} confidence` : "confidence"}>
      {label ? `${label} ` : ""}
      {Math.round(value * 100)}%
    </span>
  );
}

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-secondary",
  approved: "bg-success",
  rejected: "bg-danger",
};

export function QuestionStatusBadge({ status }: { status: string }) {
  return <span className={`badge ${STATUS_STYLES[status] ?? "bg-secondary"}`}>{status}</span>;
}
