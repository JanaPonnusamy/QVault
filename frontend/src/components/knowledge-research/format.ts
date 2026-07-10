import { KnowledgeSession } from "../../types/knowledgeResearch";

/** SQLite datetime('now') stores "YYYY-MM-DD HH:MM:SS" in UTC. */
export function parseUtc(value: string): Date {
    return new Date(value.replace(" ", "T") + "Z");
}

export function formatDuration(totalSeconds: number): string {
    const seconds = Math.max(0, Math.floor(totalSeconds));
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const rest = seconds % 60;

    if (hours > 0) {
        return `${hours}h ${minutes}m`;
    }

    if (minutes > 0) {
        return `${minutes}m ${rest}s`;
    }

    return `${rest}s`;
}

export function formatDateTime(value: string): string {
    return parseUtc(value).toLocaleString();
}

/** Wall-clock duration for finished sessions; null while queued/running. */
export function sessionDurationSeconds(
    session: KnowledgeSession
): number | null {
    if (session.status === "QUEUED" || session.status === "RUNNING") {
        return null;
    }

    return (
        (parseUtc(session.updated_at).getTime() -
            parseUtc(session.created_at).getTime()) /
        1000
    );
}

export function statusBadgeClass(status: string): string {
    switch (status) {
        case "COMPLETED":
            return "text-bg-success";
        case "FAILED":
            return "text-bg-danger";
        case "CANCELLED":
            return "text-bg-secondary";
        case "RUNNING":
            return "text-bg-warning";
        default:
            return "text-bg-light border text-secondary";
    }
}
