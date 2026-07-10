export interface KnowledgeSession {
    id: number;
    mode: string;
    input_value: string;
    source_count_requested: number;
    source_type: string;
    ai_provider: string;
    ai_model: string;
    status: string;
    current_stage: string;
    progress: number;
    storage_directory: string;
    pipeline_version: string;
    report_path: string | null;
    report_markdown_path: string | null;
    error_message: string | null;
    created_at: string;
    updated_at: string;
}

export interface DocumentAnalysis {
    summary?: string;
    recommendations?: string[];
    warnings?: string[];
    mistakes?: string[];
    timeline?: TimelineEntry[];
    confidence?: number;
}

export interface KnowledgeDocument {
    id: number;
    session_id: number;
    document_type: string;
    source_reference: string;
    title: string;
    url: string;
    language: string;
    duration: number;
    word_count: number;
    character_count: number;
    status: string;
    error_message: string | null;
    analysis: DocumentAnalysis | null;
}

export interface KnowledgeFact {
    id: number;
    document_id: number | null;
    category: string;
    subcategory: string;
    value: string;
    confidence: number;
    evidence: string;
    stage: string;
    source_document: string;
}

export interface KnowledgeEntity {
    id: number;
    document_id: number | null;
    entity_name: string;
    entity_type: string;
    category: string;
    confidence: number;
    evidence: string;
}

export interface TimelineEntry {
    step: number;
    label: string;
    detail: string;
    timing: string;
}

export interface ConsensusPractice {
    practice: string;
    supported_by: string[];
    confidence: number;
}

export interface ConsensusDifference {
    aspect: string;
    positions: { source: string; position: string }[];
}

export interface ConsensusConflict {
    topic: string;
    conflict: string;
    sources: string[];
}

export interface ConsensusRecommendation {
    summary: string;
    steps: string[];
    rationale: string;
}

export interface KnowledgeConsensus {
    id: number;
    session_id: number;
    common_practices: ConsensusPractice[] | null;
    differences: ConsensusDifference[] | null;
    conflicting_advice: ConsensusConflict[] | null;
    recommendation: ConsensusRecommendation | null;
    confidence: number;
}

export interface KnowledgeReport {
    executive_summary: string;
    recommendation: ConsensusRecommendation;
    timeline: TimelineEntry[];
    conflicts: ConsensusConflict[];
}

export interface KnowledgeResults {
    session: KnowledgeSession;
    documents: KnowledgeDocument[];
    facts: KnowledgeFact[];
    entities: KnowledgeEntity[];
    consensus: KnowledgeConsensus | null;
    report: KnowledgeReport | null;
}

export interface KnowledgeProviders {
    llm_providers: string[];
    source_types: string[];
    default_provider: string;
    default_model: string;
}

export interface SessionCreateRequest {
    mode: string;
    input_value: string;
    source_count: number;
    source_type: string;
    ai_provider: string;
    ai_model: string;
}

export interface HistoryFilters {
    status: string;
    topic: string;
    date_from: string;
    date_to: string;
    provider: string;
    source_type: string;
}
