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

export interface Job {
  id: number;
  url: string;
  title: string;
  video_id: string;
  duration: number;
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
  created_at: string;
  updated_at: string;
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
