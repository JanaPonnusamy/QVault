export interface ModuleDef {
  key: string;
  label: string;
  icon: string;
  color: string;
  path?: string;
  permission?: string;
  group: string;
  available: boolean;
}

export const MODULES: ModuleDef[] = [
  { key: "dashboard", label: "Dashboard", icon: "bi-grid-1x2", color: "#2563eb", path: "/", permission: "dashboard:view", group: "Overview", available: true },

  { key: "youtube_extractor", label: "YouTube", icon: "bi-youtube", color: "#ef4444", path: "/extractor", permission: "youtube_extractor:view", group: "Sources", available: true },
  { key: "instagram", label: "Instagram", icon: "bi-instagram", color: "#d6249f", path: "/instagram", permission: "instagram:view", group: "Sources", available: true },
  { key: "ncert", label: "NCERT", icon: "bi-journal-bookmark", color: "#0891b2", path: "/ncert", permission: "ncert:view", group: "Sources", available: true },
  { key: "pdf_import", label: "PDF", icon: "bi-file-earmark-pdf", color: "#dc2626", group: "Sources", available: false },
  { key: "image_import", label: "Images", icon: "bi-file-earmark-image", color: "#7c3aed", group: "Sources", available: false },
  { key: "previous_papers", label: "Previous Year Papers", icon: "bi-files", color: "#0d9488", group: "Question Management", available: false },

  { key: "videos", label: "Video Generation", icon: "bi-camera-video", color: "#e11d48", path: "/videos", permission: "videos:view", group: "Studio", available: true },

  { key: "documents", label: "Documents", icon: "bi-file-earmark-text", color: "#0d9488", path: "/documents", permission: "documents:view", group: "Knowledge", available: true },
  { key: "knowledge", label: "Knowledge Explorer", icon: "bi-diagram-3", color: "#7c3aed", path: "/knowledge", permission: "knowledge:view", group: "Knowledge", available: true },
  { key: "research", label: "Knowledge Research", icon: "bi-search-heart", color: "#059669", path: "/research", permission: "research:view", group: "Knowledge", available: true },

  { key: "question_bank", label: "Question Bank", icon: "bi-collection", color: "#2563eb", group: "Question Management", available: false },
  { key: "validation", label: "Question Validation", icon: "bi-check2-square", color: "#16a34a", group: "Question Management", available: false },
  { key: "classification", label: "Question Classification", icon: "bi-tags", color: "#9333ea", group: "Question Management", available: false },
  { key: "generator", label: "Question Generator", icon: "bi-stars", color: "#d97706", group: "Question Management", available: false },

  { key: "ocr", label: "OCR Management", icon: "bi-eye", color: "#0ea5e9", group: "Intelligence", available: false },
  { key: "knowledge_graph", label: "Knowledge Graph", icon: "bi-diagram-3", color: "#7c3aed", group: "Intelligence", available: false },
  { key: "syllabus", label: "Syllabus Management", icon: "bi-list-check", color: "#059669", group: "Intelligence", available: false },
  { key: "ai_models", label: "AI Models", icon: "bi-cpu", color: "#e11d48", group: "Intelligence", available: false },

  { key: "analytics", label: "Analytics", icon: "bi-graph-up", color: "#2563eb", group: "Insights", available: false },
  { key: "reports", label: "Reports", icon: "bi-file-earmark-bar-graph", color: "#0891b2", group: "Insights", available: false },

  { key: "jobs", label: "Jobs", icon: "bi-list-task", color: "#64748b", group: "Operations", available: false },
  { key: "workers", label: "Background Workers", icon: "bi-hdd-stack", color: "#475569", group: "Operations", available: false },
  { key: "monitoring", label: "System Monitoring", icon: "bi-activity", color: "#16a34a", group: "Operations", available: false },
  { key: "storage", label: "Storage", icon: "bi-hdd", color: "#64748b", group: "Operations", available: false },

  { key: "users", label: "Users", icon: "bi-people", color: "#2563eb", path: "/users", permission: "users:view", group: "Administration", available: true },
  { key: "roles", label: "Roles & Permissions", icon: "bi-shield-lock", color: "#9333ea", path: "/roles", permission: "roles:view", group: "Administration", available: true },
  { key: "api_keys", label: "API Keys", icon: "bi-key", color: "#d97706", group: "Administration", available: false },
  { key: "integrations", label: "Integrations", icon: "bi-plug", color: "#0ea5e9", group: "Administration", available: false },
  { key: "audit", label: "Audit Logs", icon: "bi-clipboard-data", color: "#475569", group: "Administration", available: false },
  { key: "settings", label: "Settings", icon: "bi-gear", color: "#64748b", path: "/settings", permission: "settings:view", group: "Administration", available: false },
];

export const MODULE_GROUPS = [...new Set(MODULES.map((m) => m.group))];
