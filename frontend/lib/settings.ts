export type AppTheme = "system" | "light" | "dark";
export type AppDensity = "comfortable" | "compact";

export type AppSettings = {
  theme: AppTheme;
  devMode: boolean;
  density: AppDensity;
  reducedMotion: boolean;
};

type PersistedAppSettingsEnvelope = {
  version: number;
  settings: Partial<AppSettings>;
};

export const APP_SETTINGS_STORAGE_KEY = "librarian.app.settings.v1";
const APP_SETTINGS_STORAGE_VERSION = 1;

export const DEFAULT_APP_SETTINGS: AppSettings = {
  theme: "system",
  devMode: true,
  density: "comfortable",
  reducedMotion: false
};

function isObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function parseTheme(value: unknown): AppTheme {
  if (value === "light" || value === "dark" || value === "system") {
    return value;
  }
  return DEFAULT_APP_SETTINGS.theme;
}

function parseDensity(value: unknown): AppDensity {
  if (value === "comfortable" || value === "compact") {
    return value;
  }
  return DEFAULT_APP_SETTINGS.density;
}

function normalizeAppSettings(input: Partial<AppSettings> | null | undefined): AppSettings {
  return {
    theme: parseTheme(input?.theme),
    devMode: typeof input?.devMode === "boolean" ? input.devMode : DEFAULT_APP_SETTINGS.devMode,
    density: parseDensity(input?.density),
    reducedMotion:
      typeof input?.reducedMotion === "boolean"
        ? input.reducedMotion
        : DEFAULT_APP_SETTINGS.reducedMotion
  };
}

function parsePersistedEnvelope(raw: unknown): PersistedAppSettingsEnvelope | null {
  if (!isObject(raw)) {
    return null;
  }
  const version = raw.version;
  const settings = raw.settings;
  if (typeof version !== "number" || !isObject(settings)) {
    return null;
  }
  return {
    version,
    settings: settings as Partial<AppSettings>
  };
}

export function readStoredAppSettings(): AppSettings {
  if (typeof window === "undefined") {
    return DEFAULT_APP_SETTINGS;
  }
  const stored = window.localStorage.getItem(APP_SETTINGS_STORAGE_KEY);
  if (!stored) {
    return DEFAULT_APP_SETTINGS;
  }

  try {
    const parsed = JSON.parse(stored) as unknown;
    const envelope = parsePersistedEnvelope(parsed);
    if (!envelope) {
      return DEFAULT_APP_SETTINGS;
    }
    if (envelope.version !== APP_SETTINGS_STORAGE_VERSION) {
      // Migration guard: unknown versions gracefully fall back to defaults.
      return DEFAULT_APP_SETTINGS;
    }
    return normalizeAppSettings(envelope.settings);
  } catch {
    return DEFAULT_APP_SETTINGS;
  }
}

export function writeStoredAppSettings(settings: AppSettings): void {
  if (typeof window === "undefined") {
    return;
  }
  const envelope: PersistedAppSettingsEnvelope = {
    version: APP_SETTINGS_STORAGE_VERSION,
    settings
  };
  window.localStorage.setItem(APP_SETTINGS_STORAGE_KEY, JSON.stringify(envelope));
}

export function resolveTheme(theme: AppTheme, prefersDark: boolean): "light" | "dark" {
  if (theme === "light") {
    return "light";
  }
  if (theme === "dark") {
    return "dark";
  }
  return prefersDark ? "dark" : "light";
}
