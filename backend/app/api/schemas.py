import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

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
        allowed = {"fixed_interval", "scene_detection", "ocr_text_change", "hybrid"}
        if value not in allowed:
            raise ValueError(f"strategy must be one of {sorted(allowed)}")
        return value

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
