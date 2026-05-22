export const THEME_STORAGE_KEY = "kaoyan-vocab-theme";
const allowedThemes = new Set(["system", "light", "dark"]);

export function getInitialTheme() {
  const stored = localStorage.getItem(THEME_STORAGE_KEY);
  return allowedThemes.has(stored) ? stored : "system";
}

export function resolveTheme(mode) {
  if (mode === "light" || mode === "dark") {
    return mode;
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function applyTheme(mode) {
  const safeMode = allowedThemes.has(mode) ? mode : "system";
  const resolved = resolveTheme(safeMode);
  document.documentElement.dataset.theme = resolved;
  document.documentElement.dataset.themePreference = safeMode;
  localStorage.setItem(THEME_STORAGE_KEY, safeMode);
}
