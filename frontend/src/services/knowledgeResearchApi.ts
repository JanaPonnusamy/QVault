import { api as apiClient } from "../api/client";

import {
    HistoryFilters,
    KnowledgeProviders,
    KnowledgeResults,
    KnowledgeSession,
    SessionCreateRequest,
} from "../types/knowledgeResearch";

export async function getProviders(): Promise<KnowledgeProviders> {
    const response = await apiClient.get("/api/research/providers");
    return response.data;
}

export async function createSession(
    request: SessionCreateRequest
): Promise<number> {
    const response = await apiClient.post(
        "/api/research/sessions",
        request
    );
    return response.data.session_id;
}

export async function getSession(
    sessionId: number
): Promise<KnowledgeSession> {
    const response = await apiClient.get(
        `/api/research/sessions/${sessionId}`
    );
    return response.data;
}

export async function getResults(
    sessionId: number
): Promise<KnowledgeResults> {
    const response = await apiClient.get(
        `/api/research/sessions/${sessionId}/results`
    );
    return response.data;
}

export async function listSessions(
    filters: Partial<HistoryFilters>
): Promise<KnowledgeSession[]> {
    const response = await apiClient.get("/api/research/sessions", {
        params: filters,
    });
    return response.data.sessions;
}

export async function getProviderModels(
    provider: string
): Promise<string[]> {
    const response = await apiClient.get(
        `/api/research/providers/${provider}/models`
    );
    return response.data.models;
}

export async function cancelSession(
    sessionId: number
): Promise<KnowledgeSession> {
    const response = await apiClient.post(
        `/api/research/sessions/${sessionId}/cancel`
    );
    return response.data;
}

export async function deleteSession(sessionId: number): Promise<void> {
    await apiClient.delete(`/api/research/sessions/${sessionId}`);
}
