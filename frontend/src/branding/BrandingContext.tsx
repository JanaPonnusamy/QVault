import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { api } from "../api/client";
import type { BrandingConfig } from "../types";

const DEFAULT_BRANDING: BrandingConfig = {
  tenant_code: "default",
  tenant_name: "Default Tenant",
  business_name: "QVault",
  app_name: "QVault Admin",
  tagline: "Exam Intelligence Platform",
  logo_text: "QVault",
  logo_icon: "bi-shield-lock-fill",
  logo_url: "",
  fonts: {
    base: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
    heading: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
    mono: "ui-monospace, SFMono-Regular, Consolas, monospace",
  },
  theme: {
    background: "#f4f6fa",
    surface: "#ffffff",
    surface_alt: "#f8fafc",
    text: "#1e293b",
    muted_text: "#64748b",
    sidebar_background: "#0f172a",
    sidebar_text: "#cbd5e1",
    sidebar_group_text: "#64748b",
    accent: "#2563eb",
    accent_contrast: "#ffffff",
    border: "#e2e8f0",
    login_background: "linear-gradient(135deg,#0f172a,#1e3a8a)",
  },
  module_colors: {},
};

type BrandingContextValue = {
  branding: BrandingConfig;
  loading: boolean;
};

const BrandingContext = createContext<BrandingContextValue>({
  branding: DEFAULT_BRANDING,
  loading: true,
});

export function BrandingProvider({ children }: { children: React.ReactNode }) {
  const [branding, setBranding] = useState<BrandingConfig>(DEFAULT_BRANDING);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    api.get<BrandingConfig>("/api/system/branding")
      .then((res) => {
        if (!mounted) return;
        setBranding(res.data);
      })
      .catch(() => {
        if (!mounted) return;
        setBranding(DEFAULT_BRANDING);
      })
      .finally(() => {
        if (!mounted) return;
        setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    applyBrandingToDocument(branding);
  }, [branding]);

  const value = useMemo(() => ({ branding, loading }), [branding, loading]);
  return <BrandingContext.Provider value={value}>{children}</BrandingContext.Provider>;
}

export function useBranding() {
  return useContext(BrandingContext);
}

function applyBrandingToDocument(branding: BrandingConfig) {
  const root = document.documentElement;
  root.style.setProperty("--qv-bg", branding.theme.background);
  root.style.setProperty("--qv-surface", branding.theme.surface);
  root.style.setProperty("--qv-surface-alt", branding.theme.surface_alt);
  root.style.setProperty("--qv-text", branding.theme.text);
  root.style.setProperty("--qv-muted-text", branding.theme.muted_text);
  root.style.setProperty("--qv-sidebar-bg", branding.theme.sidebar_background);
  root.style.setProperty("--qv-sidebar-fg", branding.theme.sidebar_text);
  root.style.setProperty("--qv-sidebar-group", branding.theme.sidebar_group_text);
  root.style.setProperty("--qv-accent", branding.theme.accent);
  root.style.setProperty("--qv-accent-contrast", branding.theme.accent_contrast);
  root.style.setProperty("--qv-border", branding.theme.border);
  root.style.setProperty("--qv-login-bg", branding.theme.login_background);
  root.style.setProperty("--qv-font-base", branding.fonts.base);
  root.style.setProperty("--qv-font-heading", branding.fonts.heading);
  root.style.setProperty("--qv-font-mono", branding.fonts.mono);
  const rgb = hexToRgb(branding.theme.accent);
  if (rgb) {
    root.style.setProperty("--bs-primary-rgb", rgb);
  }
  root.style.setProperty("--bs-primary", branding.theme.accent);
  root.style.setProperty("--bs-link-color", branding.theme.accent);
  root.style.setProperty("--bs-link-hover-color", branding.theme.accent);
  document.title = branding.app_name;
}

function hexToRgb(value: string): string | null {
  const normalized = value.trim();
  const short = /^#([a-f\d]{3})$/i.exec(normalized);
  const full = /^#([a-f\d]{6})$/i.exec(normalized);
  if (short) {
    const expanded = short[1].split("").map((part) => part + part).join("");
    return `${parseInt(expanded.slice(0, 2), 16)}, ${parseInt(expanded.slice(2, 4), 16)}, ${parseInt(expanded.slice(4, 6), 16)}`;
  }
  if (full) {
    return `${parseInt(full[1].slice(0, 2), 16)}, ${parseInt(full[1].slice(2, 4), 16)}, ${parseInt(full[1].slice(4, 6), 16)}`;
  }
  return null;
}
