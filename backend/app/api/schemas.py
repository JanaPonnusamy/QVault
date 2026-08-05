import json
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.frame_extraction_service import STRATEGIES

VALID_SAMPLING_FPS = {None, 30.0, 15.0, 10.0, 5.0, 2.0, 1.0}


def _check_sampling_fps(value: float | None) -> float | None:
    if value not in VALID_SAMPLING_FPS:
        raise ValueError(
            f"sampling_fps must be one of {sorted(v for v in VALID_SAMPLING_FPS if v is not None)} or null"
        )
    return value


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PermissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    module: str
    action: str
    code: str
    description: str


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str
    is_system: bool
    permissions: list[PermissionOut] = []


class RoleCreate(BaseModel):
    name: str
    description: str = ""
    permission_ids: list[int] = []


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    permission_ids: list[int] | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    email: str
    full_name: str
    is_active: bool
    is_superuser: bool
    role: RoleOut | None = None


class CurrentUserOut(UserOut):
    permissions: list[str] = []


class UserCreate(BaseModel):
    username: str
    email: str
    full_name: str = ""
    password: str
    role_id: int | None = None
    is_active: bool = True


class UserUpdate(BaseModel):
    email: str | None = None
    full_name: str | None = None
    password: str | None = None
    role_id: int | None = None
    is_active: bool | None = None


class JobCreate(BaseModel):
    url: str
    strategy: str = "hybrid"
    interval: float | None = None
    scene_threshold: float = 0.35
    sampling_fps: float | None = 10.0
    max_frames: int | None = None
    remove_duplicates: bool = True
    keep_best_quality: bool = True
    ignore_blank: bool = True
    ignore_blurred: bool = True

    @field_validator("strategy")
    @classmethod
    def _valid_strategy(cls, value: str) -> str:
        if value not in STRATEGIES:
            raise ValueError(f"strategy must be one of {sorted(STRATEGIES)}")
        return value


class QueueCreate(JobCreate):
    """Same extraction options as JobCreate, but `url` is a hashtag/profile
    page to auto-queue several acquisitions from (e.g.
    `https://www.instagram.com/explore/tags/<tag>/`)."""

    limit: int = Field(default=10, ge=1, le=50)

    @field_validator("sampling_fps")
    @classmethod
    def _valid_sampling_fps(cls, value: float | None) -> float | None:
        return _check_sampling_fps(value)


class EstimateRequest(BaseModel):
    url: str
    sampling_fps: float | None = 10.0

    @field_validator("sampling_fps")
    @classmethod
    def _valid_sampling_fps(cls, value: float | None) -> float | None:
        return _check_sampling_fps(value)


class EstimateResponse(BaseModel):
    duration: float
    fps: float
    estimated_frames: int


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    url: str
    source: str = "youtube"
    title: str
    video_id: str
    duration: int
    caption: str = ""
    author: str = ""
    upload_date: str = ""
    thumbnail_url: str = ""
    extraction_strategy: str = "hybrid"
    status: str
    stage: str
    progress: int
    error: str
    frame_count: int
    created_at: datetime
    updated_at: datetime


class FrameOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    job_id: int
    index: int
    timestamp: float
    question_score: float = 0.0
    is_question: bool = False
    is_duplicate: bool = False
    ocr_text: str = ""
    ocr_confidence: float = 0.0
    ocr_done: bool = False
    classification: list[str] = []

    @field_validator("classification", mode="before")
    @classmethod
    def _parse_classification(cls, value):
        if isinstance(value, str):
            if not value.strip():
                return []
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, list) else []
            except json.JSONDecodeError:
                return []
        return value or []


class InstagramStats(BaseModel):
    total: int = 0
    completed: int = 0
    processing: int = 0
    failed: int = 0
    frames: int = 0


class InstagramLoginRequest(BaseModel):
    username: str
    password: str


class InstagramLoginStatus(BaseModel):
    connected: bool = False
    username: str | None = None
    connected_at: str | None = None


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    job_id: int
    frame_id: int | None
    text: str
    options: list[str] = []
    timestamp: float
    source: str = "manual"
    status: str = "pending"
    ocr_confidence: float = 0.0
    frame_confidence: float = 0.0
    merge_confidence: float = 0.0
    overall_confidence: float = 0.0
    frame_start: int | None = None
    frame_end: int | None = None

    @field_validator("options", mode="before")
    @classmethod
    def _parse_options(cls, value):
        if isinstance(value, str):
            if not value.strip():
                return []
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, list) else []
            except json.JSONDecodeError:
                return []
        return value or []


class QuestionUpdate(BaseModel):
    text: str | None = None
    options: list[str] | None = None
    status: str | None = None


class OcrRequest(BaseModel):
    frame_ids: list[int]


class AnalyzeSummary(BaseModel):
    frames_total: int = 0
    frames_unique: int = 0
    frames_question: int = 0
    questions_created: int = 0


# ---------- NCERT acquisition ----------

class NcertBookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    book_code: str
    class_level: str
    class_label: str
    subject: str
    title: str
    part: str
    language: str
    url: str
    edition: str
    cover_url: str
    status: str
    downloaded: bool
    downloaded_at: datetime | None = None
    last_checked: datetime | None = None
    file_size: int
    checksum: str
    version_hash: str
    error: str


class NcertFacets(BaseModel):
    classes: list[str] = []
    subjects: list[str] = []
    languages: list[str] = []
    statuses: list[str] = []


class NcertBookList(BaseModel):
    items: list[NcertBookOut]
    total: int
    limit: int
    offset: int


class NcertStats(BaseModel):
    total: int = 0
    downloaded: int = 0
    available: int = 0
    pending: int = 0
    failed: int = 0
    update_available: int = 0


class AcquisitionJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source: str
    job_type: str
    status: str
    stage: str
    progress: int
    total: int
    processed: int
    error: str
    payload: str = ""
    created_at: datetime
    updated_at: datetime


class DownloadRequest(BaseModel):
    book_ids: list[int]


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    level: str
    title: str
    message: str
    source: str
    is_read: bool
    created_at: datetime


class NotificationList(BaseModel):
    items: list[NotificationOut]
    unread: int


# ---------- Knowledge Extraction / Documents ----------

class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source: str
    source_ref: str
    title: str
    file_type: str
    page_count: int
    has_text_layer: bool
    needs_ocr: bool
    status: str
    element_count: int
    error: str
    created_at: datetime
    processed_at: datetime | None = None


class DocumentBookmarkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    level: int
    title: str
    page: int
    order_index: int


class DocumentElementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    page: int
    order_index: int
    element_type: str
    level: int | None
    text: str
    bbox: list[float] = []
    extra: dict | None = None

    @field_validator("bbox", mode="before")
    @classmethod
    def _bbox(cls, value):
        if isinstance(value, str):
            if not value.strip():
                return []
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return []
        return value or []

    @field_validator("extra", mode="before")
    @classmethod
    def _extra(cls, value):
        if isinstance(value, str):
            if not value.strip():
                return None
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return value


class DocumentDetail(DocumentOut):
    bookmarks: list[DocumentBookmarkOut] = []


class DocumentList(BaseModel):
    items: list[DocumentOut]
    total: int
    limit: int
    offset: int


class DocumentStats(BaseModel):
    total: int = 0
    processed: int = 0
    pending: int = 0
    failed: int = 0
    needs_ocr: int = 0
    elements: int = 0


class ImportNcertRequest(BaseModel):
    book_id: int


class DownloadedBookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    book_code: str
    title: str
    class_label: str


# ---------- Knowledge Mapping ----------

class KnowledgeNodeBase(BaseModel):
    id: int
    document_id: int
    parent_id: int | None = None
    node_type: str
    title: str
    level: int | None = None
    depth: int
    order_index: int
    page: int


class KnowledgeTreeNode(KnowledgeNodeBase):
    children: list["KnowledgeTreeNode"] = []


class BreadcrumbItem(BaseModel):
    id: int
    title: str


class KnowledgeNodeDetail(KnowledgeNodeBase):
    content: str = ""
    extra: dict | None = None
    breadcrumb: list[BreadcrumbItem] = []
    children: list[KnowledgeNodeBase] = []


class KnowledgeSearchResult(KnowledgeNodeBase):
    content: str = ""
    document_title: str = ""
    breadcrumb: list[str] = []


class MappedDocumentOut(BaseModel):
    id: int
    title: str
    source: str
    status: str
    page_count: int
    node_count: int


class KnowledgeStats(BaseModel):
    mapped_documents: int = 0
    nodes: int = 0
    sections: int = 0
    paragraphs: int = 0
    tables: int = 0
    figures: int = 0


KnowledgeTreeNode.model_rebuild()


# ---------- Content Assembly / Reader ----------

class ContentBlockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    section_id: int | None
    block_type: str
    order_index: int
    text: str
    caption: str
    page: int
    source_element_ids: list[int] = []
    extra: dict | None = None

    @field_validator("source_element_ids", mode="before")
    @classmethod
    def _ids(cls, value):
        if isinstance(value, str):
            if not value.strip():
                return []
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return []
        return value or []

    @field_validator("extra", mode="before")
    @classmethod
    def _extra(cls, value):
        if isinstance(value, str):
            if not value.strip():
                return None
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return value


class ContentSectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    parent_id: int | None
    title: str
    level: int
    order_index: int
    page_start: int
    page_end: int
    blocks: list[ContentBlockOut] = []


class AssembledDocumentOut(BaseModel):
    document_id: int
    title: str
    section_count: int
    block_count: int
    sections: list[ContentSectionOut] = []


class ContentStats(BaseModel):
    assembled_documents: int = 0
    sections: int = 0
    blocks: int = 0
    paragraphs: int = 0
    figures: int = 0
    tables: int = 0
    examples: int = 0
    exercises: int = 0


class AssembleSummary(BaseModel):
    sections: int = 0
    blocks: int = 0
    dropped_noise: int = 0


# ---------------------------------------------------------------- Video Generation


class VideoSourceOut(BaseModel):
    path: str
    question_count: int
    usable_count: int
    topics: dict[str, int]


class VideoTemplateOut(BaseModel):
    key: str
    name: str
    description: str = ""


class TTSVoiceOut(BaseModel):
    id: str
    label: str
    language: str = ""
    gender: str = ""


class TTSProviderOut(BaseModel):
    name: str
    label: str
    available: bool
    voices: list[TTSVoiceOut]


class VideoGenerateRequest(BaseModel):
    source_file: str
    kind: str = "video"  # video | short | reel
    orientation: str | None = None  # landscape | portrait (defaults by kind)
    category: str = "General Knowledge"
    topic: str | None = None
    question_count: int | None = Field(None, ge=1, le=50)
    offset: int = Field(0, ge=0)
    shuffle_seed: int | None = None
    template: str | None = None
    tts_provider: str | None = None
    tts_voice: str | None = None


class VideoBatchRequest(VideoGenerateRequest):
    batch_count: int = Field(10, ge=1, le=100)


class VideoPreviewRequest(BaseModel):
    source_file: str
    kind: str = "video"
    category: str = "General Knowledge"
    topic: str | None = None
    question_count: int | None = Field(None, ge=1, le=50)
    offset: int = Field(0, ge=0)
    shuffle_seed: int | None = None


class VideoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    kind: str
    orientation: str
    width: int
    height: int
    fps: int
    duration: float
    category: str
    source_file: str
    topic: str
    question_count: int
    template: str
    tts_provider: str
    tts_voice: str
    status: str
    error: str
    file_size: int
    has_srt: bool = False
    has_thumbnail: bool = False
    created_at: datetime | None = None


class VideoList(BaseModel):
    items: list[VideoOut]
    total: int
    limit: int
    offset: int


class VideoStats(BaseModel):
    total: int = 0
    completed: int = 0
    failed: int = 0
    in_progress: int = 0
    videos: int = 0
    shorts: int = 0
    reels: int = 0
    total_duration: float = 0


# ---------- Syllabus Catalog ----------

class TopicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str
    display_order: int


class ChapterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    unit_id: uuid.UUID
    code: str
    name: str
    display_order: int


class ChapterTreeOut(ChapterOut):
    topics: list[TopicOut] = []


class UnitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    subject_id: uuid.UUID
    code: str
    name: str
    display_order: int


class UnitTreeOut(UnitOut):
    chapters: list[ChapterTreeOut] = []


class SubjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    exam_id: uuid.UUID
    code: str
    name: str
    display_order: int


class SubjectTreeOut(SubjectOut):
    units: list[UnitTreeOut] = []


class ExamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str
    description: str
    display_order: int
    is_active: bool


class ExamTreeOut(ExamOut):
    subjects: list[SubjectTreeOut] = []


class CatalogStats(BaseModel):
    exams: int = 0
    subjects: int = 0
    units: int = 0
    chapters: int = 0
    topics: int = 0


class SyllabusImportLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    exam_code: str
    source_file: str
    status: str
    subjects_count: int
    units_count: int
    chapters_count: int
    topics_count: int
    created_count: int
    updated_count: int
    error: str
    started_at: datetime
    finished_at: datetime | None = None
    total_size: int = 0


# ---------- Question Bank ----------

QUESTION_TYPES = {
    "mcq", "msq", "nat", "numerical", "assertion_reason",
    "match_following", "matrix_match", "paragraph",
    "essay", "fill_blank",
}
QUESTION_STATUSES = {"draft", "pending_review", "approved", "rejected", "duplicate"}


class BankQuestionTopicIn(BaseModel):
    subject_id: uuid.UUID | None = None
    unit_id: uuid.UUID | None = None
    chapter_id: uuid.UUID | None = None
    topic_id: uuid.UUID | None = None
    is_primary: bool = False


class BankQuestionTopicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    subject_id: uuid.UUID | None
    unit_id: uuid.UUID | None
    chapter_id: uuid.UUID | None
    topic_id: uuid.UUID | None
    is_primary: bool


class BankQuestionOptionIn(BaseModel):
    label: str = ""
    text: str = ""
    image_path: str = ""
    is_correct: bool = False


class BankQuestionOptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    label: str
    text: str
    image_path: str
    is_correct: bool
    order_index: int


class BankQuestionSolutionCreate(BaseModel):
    solution_text: str
    explanation: str = ""
    source_type: str = "manual"
    source_url: str = ""


class BankQuestionSolutionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    solution_text: str
    explanation: str
    source_type: str
    source_url: str
    confidence: float
    created_at: datetime


class BankQuestionImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    image_path: str
    image_type: str
    caption: str
    sha256_hash: str
    phash: str


class BankQuestionLineageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    stage: str
    detail: str
    created_by: int | None
    created_at: datetime


class BankSourceIn(BaseModel):
    provider: str = "manual"
    website: str = ""
    url: str
    exam: str = ""
    year: int | None = None
    shift: str = ""
    language: str = ""
    license: str = ""
    checksum: str = ""


class BankSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    provider: str
    website: str
    url: str
    exam: str
    year: int | None
    shift: str
    language: str
    license: str
    checksum: str
    first_seen: datetime
    last_seen: datetime
    crawl_count: int
    last_status: str


class BankQuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    exam: str
    exam_id: uuid.UUID | None
    year: int | None
    session: str
    shift: str
    difficulty: str
    question_type: str
    question_text: str
    language: str
    correct_answer_text: str
    image_exists: bool
    image_path: str
    status: str
    current_stage: str
    review_reason: str
    confidence: float
    duplicate_score: float
    source_id: uuid.UUID | None
    created_on: datetime
    modified_on: datetime


class BankQuestionDetail(BankQuestionOut):
    answer_data: str
    question_hash: str
    normalized_text: str
    topics: list[BankQuestionTopicOut] = []
    options: list[BankQuestionOptionOut] = []
    solutions: list[BankQuestionSolutionOut] = []
    images: list[BankQuestionImageOut] = []
    lineage: list[BankQuestionLineageOut] = []
    source: BankSourceOut | None = None


class BankQuestionCreate(BaseModel):
    exam: str = ""
    exam_id: uuid.UUID | None = None
    year: int | None = None
    session: str = ""
    shift: str = ""
    difficulty: str = ""
    question_type: str = "mcq"
    question_text: str
    language: str = "en"
    correct_answer_text: str = ""
    answer_data: str = ""
    image_exists: bool = False
    image_path: str = ""
    status: str = "draft"
    confidence: float = 0.0
    topics: list[BankQuestionTopicIn] = []
    options: list[BankQuestionOptionIn] = []
    solution_text: str = ""
    solution_source_type: str = "manual"
    source: BankSourceIn | None = None

    @field_validator("question_text")
    @classmethod
    def _non_empty_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question_text must not be empty")
        return value

    @field_validator("question_type")
    @classmethod
    def _valid_type(cls, value: str) -> str:
        if value not in QUESTION_TYPES:
            raise ValueError(f"question_type must be one of {sorted(QUESTION_TYPES)}")
        return value

    @field_validator("status")
    @classmethod
    def _valid_status(cls, value: str) -> str:
        if value not in QUESTION_STATUSES:
            raise ValueError(f"status must be one of {sorted(QUESTION_STATUSES)}")
        return value


class BankQuestionUpdate(BaseModel):
    exam: str | None = None
    exam_id: uuid.UUID | None = None
    year: int | None = None
    session: str | None = None
    shift: str | None = None
    difficulty: str | None = None
    question_type: str | None = None
    question_text: str | None = None
    language: str | None = None
    correct_answer_text: str | None = None
    answer_data: str | None = None
    image_exists: bool | None = None
    image_path: str | None = None
    status: str | None = None
    confidence: float | None = None
    topics: list[BankQuestionTopicIn] | None = None
    options: list[BankQuestionOptionIn] | None = None

    @field_validator("question_type")
    @classmethod
    def _valid_type(cls, value: str | None) -> str | None:
        if value is not None and value not in QUESTION_TYPES:
            raise ValueError(f"question_type must be one of {sorted(QUESTION_TYPES)}")
        return value

    @field_validator("status")
    @classmethod
    def _valid_status(cls, value: str | None) -> str | None:
        if value is not None and value not in QUESTION_STATUSES:
            raise ValueError(f"status must be one of {sorted(QUESTION_STATUSES)}")
        return value


class BankQuestionList(BaseModel):
    items: list[BankQuestionOut]
    total: int
    limit: int
    offset: int


class BankQuestionStats(BaseModel):
    total: int = 0
    draft: int = 0
    pending_review: int = 0
    approved: int = 0
    rejected: int = 0
    duplicate: int = 0
    with_solution: int = 0
    with_image: int = 0
    needs_review: int = 0
    sources: int = 0
    by_type: dict[str, int] = {}


class GkScanRequest(BaseModel):
    homepage_url: str


class GkProfileOut(BaseModel):
    domain: str
    content: str
    updated_at: datetime


class GkProfileList(BaseModel):
    domains: list[str]


class GkVisitedUrlOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source_url: str
    document_type: str
    status: str
    error: str
    discovered_at: datetime
    updated_at: datetime


class GkVisitedUrlList(BaseModel):
    total: int
    items: list[GkVisitedUrlOut]


class GkSiteReportOut(BaseModel):
    domain: str
    homepage_url: str
    status: str
    total_pages: int
    scraped_pages: int
    failed_pages: int
    questions: int
    options: int
    last_scanned: datetime | None = None


class GkSiteReportList(BaseModel):
    sites: list[GkSiteReportOut]


# ---------- Education Acquisition ----------

EDUCATION_PROVIDER_CODES = {
    "manual_url",
    "sitemap",
    "website_crawl",
    "rss",
    "government_portal",
    "pdf_discovery",
    "document_discovery",
    "google",
    "bing",
    "duckduckgo",
}


class EducationScanRequest(BaseModel):
    queries: list[str] = []
    manual_urls: list[str] = []
    root_urls: list[str] = []
    rss_urls: list[str] = []
    government_urls: list[str] = []
    providers: list[str] = ["manual_url", "sitemap", "website_crawl", "pdf_discovery", "document_discovery", "duckduckgo"]
    max_pages_per_root: int = Field(50, ge=1, le=500)
    max_search_results: int = Field(30, ge=1, le=200)

    @field_validator("providers")
    @classmethod
    def _valid_providers(cls, value: list[str]) -> list[str]:
        bad = [item for item in value if item not in EDUCATION_PROVIDER_CODES]
        if bad:
            raise ValueError(f"Unknown providers: {', '.join(sorted(bad))}")
        return value


class EducationStatsOut(BaseModel):
    sources: int = 0
    documents: int = 0
    fields: int = 0
    forms: int = 0


class EducationSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    source_key: str
    institution_name: str
    institution_type: str
    board: str
    state: str
    district: str
    website_url: str
    source_kind: str
    is_government: str
    created_at: datetime
    updated_at: datetime


class EducationSourceList(BaseModel):
    items: list[EducationSourceOut]
    total: int
    limit: int
    offset: int


class EducationDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    source_id: str | None
    acquisition_item_id: int | None
    url: str
    title: str
    document_type: str
    classification: str
    file_type: str
    checksum: str
    local_file: str
    language: str
    summary: str
    created_at: datetime
    updated_at: datetime


class EducationFieldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    canonical_key: str
    label: str
    value: str
    value_type: str
    source_kind: str
    confidence: float
    order_index: int


class EducationFieldCatalogItemOut(BaseModel):
    key: str
    label: str
    stage: str
    required: bool
    description: str


class EducationFieldValueOut(BaseModel):
    value: str
    label: str
    source_kind: str
    confidence: float


class EducationFieldCoverageOut(EducationFieldCatalogItemOut):
    present: bool = False
    values: list[EducationFieldValueOut] = []


class EducationFieldCatalogOut(BaseModel):
    enquiry_fields: list[EducationFieldCatalogItemOut] = []
    application_fields: list[EducationFieldCatalogItemOut] = []
    notes: list[str] = []


class EducationFieldSummaryOut(BaseModel):
    enquiry_fields: list[EducationFieldCoverageOut] = []
    application_fields: list[EducationFieldCoverageOut] = []
    custom_fields: list[dict] = []
    raw_metadata_fields: list[dict] = []
    missing_required_enquiry: list[str] = []
    missing_required_application: list[str] = []
    supports_custom_fields: bool = True


class EducationDocumentDetail(EducationDocumentOut):
    fields: list[EducationFieldOut] = []
    tags: list[str] = []
    source: EducationSourceOut | None = None
    metadata: dict = {}
    field_summary: EducationFieldSummaryOut = Field(default_factory=EducationFieldSummaryOut)


class EducationDocumentList(BaseModel):
    items: list[EducationDocumentOut]
    total: int
    limit: int
    offset: int


# ---------- Branding / Tenant UI ----------

class BrandingFontsOut(BaseModel):
    base: str
    heading: str
    mono: str


class BrandingThemeOut(BaseModel):
    background: str
    surface: str
    surface_alt: str
    text: str
    muted_text: str
    sidebar_background: str
    sidebar_text: str
    sidebar_group_text: str
    accent: str
    accent_contrast: str
    border: str
    login_background: str


class BrandingConfigOut(BaseModel):
    tenant_code: str
    tenant_name: str
    business_name: str
    app_name: str
    tagline: str
    logo_text: str
    logo_icon: str
    logo_url: str
    fonts: BrandingFontsOut
    theme: BrandingThemeOut
    module_colors: dict[str, str] = {}
