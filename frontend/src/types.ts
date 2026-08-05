export interface Permission {
  id: number;
  module: string;
  action: string;
  code: string;
  description: string;
}

export interface Role {
  id: number;
  name: string;
  description: string;
  is_system: boolean;
  permissions: Permission[];
}

export interface User {
  id: number;
  username: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_superuser: boolean;
  role: Role | null;
}

export interface CurrentUser extends User {
  permissions: string[];
}

export interface BrandingFonts {
  base: string;
  heading: string;
  mono: string;
}

export interface BrandingTheme {
  background: string;
  surface: string;
  surface_alt: string;
  text: string;
  muted_text: string;
  sidebar_background: string;
  sidebar_text: string;
  sidebar_group_text: string;
  accent: string;
  accent_contrast: string;
  border: string;
  login_background: string;
}

export interface BrandingConfig {
  tenant_code: string;
  tenant_name: string;
  business_name: string;
  app_name: string;
  tagline: string;
  logo_text: string;
  logo_icon: string;
  logo_url: string;
  fonts: BrandingFonts;
  theme: BrandingTheme;
  module_colors: Record<string, string>;
}

export type FrameExtractionStrategy = "fixed_interval" | "scene_detection" | "ocr_text_change" | "hybrid" | "all_frames";

// null = "every decoded frame" (catches sub-300ms flash content).
export type SamplingFps = 30 | 15 | 10 | 5 | 2 | 1 | null;

export interface ExtractionOptions {
  strategy: FrameExtractionStrategy;
  interval: number | null;
  scene_threshold: number;
  sampling_fps: SamplingFps;
  max_frames: number | null;
  remove_duplicates: boolean;
  keep_best_quality: boolean;
  ignore_blank: boolean;
  ignore_blurred: boolean;
}

export const DEFAULT_EXTRACTION_OPTIONS: ExtractionOptions = {
  strategy: "hybrid",
  interval: null,
  scene_threshold: 0.35,
  sampling_fps: 10,
  max_frames: null,
  remove_duplicates: true,
  keep_best_quality: true,
  ignore_blank: true,
  ignore_blurred: true,
};

export interface EstimateResponse {
  duration: number;
  fps: number;
  estimated_frames: number;
}

export interface Job {
  id: number;
  url: string;
  source: string;
  title: string;
  video_id: string;
  duration: number;
  caption: string;
  author: string;
  upload_date: string;
  thumbnail_url: string;
  extraction_strategy: string;
  status: string;
  stage: string;
  progress: number;
  error: string;
  frame_count: number;
  created_at: string;
  updated_at: string;
}

export interface Frame {
  id: number;
  job_id: number;
  index: number;
  timestamp: number;
  question_score: number;
  is_question: boolean;
  is_duplicate: boolean;
  ocr_text?: string;
  ocr_confidence?: number;
  ocr_done?: boolean;
  classification?: string[];
}

export interface InstagramStats {
  total: number;
  completed: number;
  processing: number;
  failed: number;
  frames: number;
}

export interface InstagramLoginStatus {
  connected: boolean;
  username: string | null;
  connected_at: string | null;
}

export interface NcertBook {
  id: number;
  book_code: string;
  class_level: string;
  class_label: string;
  subject: string;
  title: string;
  part: string;
  language: string;
  url: string;
  edition: string;
  cover_url: string;
  status: string;
  downloaded: boolean;
  downloaded_at: string | null;
  last_checked: string | null;
  file_size: number;
  checksum: string;
  version_hash: string;
  error: string;
}

export interface NcertStats {
  total: number;
  downloaded: number;
  available: number;
  pending: number;
  failed: number;
  update_available: number;
}

export interface NcertFacets {
  classes: string[];
  subjects: string[];
  languages: string[];
  statuses: string[];
}

export interface AcquisitionJob {
  id: number;
  source: string;
  job_type: string;
  status: string;
  stage: string;
  progress: number;
  total: number;
  processed: number;
  error: string;
  payload: string;
  created_at: string;
  updated_at: string;
}

export interface GkProfile {
  domain: string;
  content: string;
  updated_at: string;
}

export interface GkVisitedUrl {
  id: number;
  source_url: string;
  document_type: string;
  status: string;
  error: string;
  discovered_at: string;
  updated_at: string;
}

export interface GkVisitedUrlList {
  total: number;
  items: GkVisitedUrl[];
}

export interface GkSiteReport {
  domain: string;
  homepage_url: string;
  status: "not_started" | "queued" | "scanning" | "downloading" | "completed" | "partial" | "failed" | string;
  total_pages: number;
  scraped_pages: number;
  failed_pages: number;
  questions: number;
  options: number;
  last_scanned: string | null;
}

export interface DocItem {
  id: number;
  source: string;
  source_ref: string;
  title: string;
  file_type: string;
  page_count: number;
  has_text_layer: boolean;
  needs_ocr: boolean;
  status: string;
  element_count: number;
  error: string;
  created_at: string;
  processed_at: string | null;
}

export interface DocBookmark {
  id: number;
  level: number;
  title: string;
  page: number;
  order_index: number;
}

export interface DocDetail extends DocItem {
  bookmarks: DocBookmark[];
}

export interface DocElement {
  id: number;
  page: number;
  order_index: number;
  element_type: string;
  level: number | null;
  text: string;
  bbox: number[];
  extra: { rows?: string[][]; n_rows?: number; n_cols?: number; width?: number; height?: number } | null;
}

export interface DocStats {
  total: number;
  processed: number;
  pending: number;
  failed: number;
  needs_ocr: number;
  elements: number;
}

export interface ContentBlock {
  id: number;
  section_id: number | null;
  block_type: string;
  order_index: number;
  text: string;
  caption: string;
  page: number;
  source_element_ids: number[];
  extra: { rows?: string[][]; n_rows?: number; n_cols?: number; width?: number; height?: number } | null;
}

export interface ContentSection {
  id: number;
  parent_id: number | null;
  title: string;
  level: number;
  order_index: number;
  page_start: number;
  page_end: number;
  blocks: ContentBlock[];
}

export interface AssembledDocument {
  document_id: number;
  title: string;
  section_count: number;
  block_count: number;
  sections: ContentSection[];
}

export interface DownloadedBook {
  id: number;
  book_code: string;
  title: string;
  class_label: string;
}

export interface KnowledgeNodeBase {
  id: number;
  document_id: number;
  parent_id: number | null;
  node_type: string;
  title: string;
  level: number | null;
  depth: number;
  order_index: number;
  page: number;
}

export interface KnowledgeTreeNode extends KnowledgeNodeBase {
  children: KnowledgeTreeNode[];
}

export interface KnowledgeNodeDetail extends KnowledgeNodeBase {
  content: string;
  extra: { rows?: string[][]; n_rows?: number; n_cols?: number; width?: number; height?: number } | null;
  breadcrumb: { id: number; title: string }[];
  children: KnowledgeNodeBase[];
}

export interface KnowledgeSearchResult extends KnowledgeNodeBase {
  content: string;
  document_title: string;
  breadcrumb: string[];
}

export interface MappedDocument {
  id: number;
  title: string;
  source: string;
  status: string;
  page_count: number;
  node_count: number;
}

export interface KnowledgeStats {
  mapped_documents: number;
  nodes: number;
  sections: number;
  paragraphs: number;
  tables: number;
  figures: number;
}

export interface Notification {
  id: number;
  level: string;
  title: string;
  message: string;
  source: string;
  is_read: boolean;
  created_at: string;
}

export interface Question {
  id: number;
  job_id: number;
  frame_id: number | null;
  text: string;
  options: string[];
  timestamp: number;
  source: string;
  status: string;
  ocr_confidence: number;
  frame_confidence: number;
  merge_confidence: number;
  overall_confidence: number;
  frame_start: number | null;
  frame_end: number | null;
}

export interface VideoStats {
  total: number;
  completed: number;
  failed: number;
  in_progress: number;
  videos: number;
  shorts: number;
  reels: number;
  total_duration: number;
  total_size: number;
}

export interface VideoItem {
  id: number;
  title: string;
  kind: string;
  orientation: string;
  width: number;
  height: number;
  fps: number;
  duration: number;
  category: string;
  source_file: string;
  topic: string;
  question_count: number;
  template: string;
  tts_provider: string;
  tts_voice: string;
  status: string;
  error: string;
  file_size: number;
  has_srt: boolean;
  has_thumbnail: boolean;
  created_at: string | null;
}

export interface VideoSource {
  path: string;
  question_count: number;
  usable_count: number;
  topics: Record<string, number>;
}

export interface VideoTemplate {
  key: string;
  name: string;
  description: string;
}

export interface TTSVoice {
  id: string;
  label: string;
  language: string;
  gender: string;
}

export interface TTSProviderInfo {
  name: string;
  label: string;
  available: boolean;
  voices: TTSVoice[];
}

export interface TimelineScenePreview {
  index: number;
  question: string;
  answer: string;
  question_in: number;
  options_in: number[];
  think_in: number;
  countdown_in: number;
  reveal_at: number;
  answer_in: number;
  explanation_in: number | null;
  end: number;
}

export interface TimelinePreview {
  kind: string;
  category: string;
  duration: number;
  intro_end: number;
  outro_in: number;
  scenes: TimelineScenePreview[];
}

export interface CatalogStats {
  exams: number;
  subjects: number;
  units: number;
  chapters: number;
  topics: number;
}

export interface ExamOut {
  id: string;
  code: string;
  name: string;
  description: string;
  display_order: number;
  is_active: boolean;
}

export interface SubjectOut {
  id: string;
  exam_id: string;
  code: string;
  name: string;
  display_order: number;
}

export interface UnitOut {
  id: string;
  subject_id: string;
  code: string;
  name: string;
  display_order: number;
}

export interface ChapterOut {
  id: string;
  unit_id: string;
  code: string;
  name: string;
  display_order: number;
}

export interface TopicOut {
  id: string;
  chapter_id: string;
  code: string;
  name: string;
  display_order: number;
}

export interface SyllabusImportLogOut {
  id: string;
  exam_code: string;
  source_file: string;
  status: string;
  subjects_count: number;
  units_count: number;
  chapters_count: number;
  topics_count: number;
  created_count: number;
  updated_count: number;
  error: string;
  started_at: string;
  finished_at: string | null;
}

// ---------- Question Bank ----------

export const QUESTION_TYPES = [
  "mcq", "msq", "nat", "numerical", "assertion_reason",
  "match_following", "matrix_match", "paragraph",
  "essay", "fill_blank",
] as const;
export type QuestionType = (typeof QUESTION_TYPES)[number];

export const QUESTION_STATUSES = ["draft", "pending_review", "approved", "rejected", "duplicate"] as const;
export type QuestionStatus = (typeof QUESTION_STATUSES)[number];

export interface BankQuestionTopic {
  id: number;
  subject_id: string | null;
  unit_id: string | null;
  chapter_id: string | null;
  topic_id: string | null;
  is_primary: boolean;
}

export interface BankQuestionOption {
  id: number;
  label: string;
  text: string;
  image_path: string;
  is_correct: boolean;
  order_index: number;
}

export interface BankQuestionSolution {
  id: number;
  solution_text: string;
  explanation: string;
  source_type: string;
  source_url: string;
  confidence: number;
  created_at: string;
}

export interface BankQuestionImage {
  id: number;
  image_path: string;
  image_type: string;
  caption: string;
  sha256_hash: string;
  phash: string;
}

export interface BankQuestionLineage {
  id: number;
  stage: string;
  detail: string;
  created_by: number | null;
  created_at: string;
}

export interface BankSource {
  id: string;
  provider: string;
  website: string;
  url: string;
  exam: string;
  year: number | null;
  shift: string;
  language: string;
  license: string;
  checksum: string;
  first_seen: string;
  last_seen: string;
  crawl_count: number;
  last_status: string;
}

export interface BankQuestion {
  id: string;
  exam: string;
  exam_id: string | null;
  year: number | null;
  session: string;
  shift: string;
  difficulty: string;
  question_type: string;
  question_text: string;
  language: string;
  correct_answer_text: string;
  image_exists: boolean;
  image_path: string;
  status: string;
  current_stage: string;
  review_reason: string;
  confidence: number;
  duplicate_score: number;
  source_id: string | null;
  created_on: string;
  modified_on: string;
}

export interface BankQuestionDetail extends BankQuestion {
  answer_data: string;
  question_hash: string;
  normalized_text: string;
  topics: BankQuestionTopic[];
  options: BankQuestionOption[];
  solutions: BankQuestionSolution[];
  images: BankQuestionImage[];
  lineage: BankQuestionLineage[];
  source: BankSource | null;
}

export interface BankQuestionList {
  items: BankQuestion[];
  total: number;
  limit: number;
  offset: number;
}

export interface BankQuestionStats {
  total: number;
  draft: number;
  pending_review: number;
  approved: number;
  rejected: number;
  duplicate: number;
  with_solution: number;
  with_image: number;
  needs_review: number;
  sources: number;
  by_type: Record<string, number>;
}

// ---------- Education Acquisition ----------

export interface EducationStats {
  sources: number;
  documents: number;
  fields: number;
  forms: number;
}

export interface EducationSource {
  id: string;
  source_key: string;
  institution_name: string;
  institution_type: string;
  board: string;
  state: string;
  district: string;
  website_url: string;
  source_kind: string;
  is_government: string;
  created_at: string;
  updated_at: string;
}

export interface EducationSourceList {
  items: EducationSource[];
  total: number;
  limit: number;
  offset: number;
}

export interface EducationDocument {
  id: string;
  source_id: string | null;
  acquisition_item_id: number | null;
  url: string;
  title: string;
  document_type: string;
  classification: string;
  file_type: string;
  checksum: string;
  local_file: string;
  language: string;
  summary: string;
  created_at: string;
  updated_at: string;
}

export interface EducationDocumentList {
  items: EducationDocument[];
  total: number;
  limit: number;
  offset: number;
}

export interface EducationField {
  id: number;
  canonical_key: string;
  label: string;
  value: string;
  value_type: string;
  source_kind: string;
  confidence: number;
  order_index: number;
}

export interface EducationFieldCatalogItem {
  key: string;
  label: string;
  stage: string;
  required: boolean;
  description: string;
}

export interface EducationFieldValue {
  value: string;
  label: string;
  source_kind: string;
  confidence: number;
}

export interface EducationFieldCoverage extends EducationFieldCatalogItem {
  present: boolean;
  values: EducationFieldValue[];
}

export interface EducationFieldCatalog {
  enquiry_fields: EducationFieldCatalogItem[];
  application_fields: EducationFieldCatalogItem[];
  notes: string[];
}

export interface EducationFieldSummary {
  enquiry_fields: EducationFieldCoverage[];
  application_fields: EducationFieldCoverage[];
  custom_fields: Array<{ key: string; label: string; value: string; source_kind: string }>;
  raw_metadata_fields: Array<{ key: string; value: string }>;
  missing_required_enquiry: string[];
  missing_required_application: string[];
  supports_custom_fields: boolean;
}

export interface EducationDocumentDetail extends EducationDocument {
  fields: EducationField[];
  tags: string[];
  source: EducationSource | null;
  metadata: Record<string, unknown>;
  field_summary: EducationFieldSummary;
}
