"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

import {
  APP_SETTINGS_STORAGE_KEY,
  type AppDensity,
  type AppSettings,
  type AppTheme,
  DEFAULT_APP_SETTINGS,
  readStoredAppSettings,
  resolveTheme,
  writeStoredAppSettings
} from "@/lib/settings";

type AppSettingsContextValue = {
  settings: AppSettings;
  setTheme: (theme: AppTheme) => void;
  setDevMode: (devMode: boolean) => void;
  setDensity: (density: AppDensity) => void;
  setReducedMotion: (reducedMotion: boolean) => void;
  setEnrichmentSources: (enrichmentSources: boolean) => void;
  resetSettings: () => void;
};

const AppSettingsContext = createContext<AppSettingsContextValue | null>(null);

function applyDocumentSettings(settings: AppSettings, prefersDark: boolean): void {
  if (typeof document === "undefined") {
    return;
  }
  const root = document.documentElement;
  const resolvedTheme = resolveTheme(settings.theme, prefersDark);
  root.classList.toggle("dark", resolvedTheme === "dark");
  root.style.colorScheme = resolvedTheme;
  root.dataset.density = settings.density;
  root.dataset.motion = settings.reducedMotion ? "reduced" : "normal";
}

export function AppSettingsProvider({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  const [settings, setSettings] = useState<AppSettings>(DEFAULT_APP_SETTINGS);
  const [hydratedFromStorage, setHydratedFromStorage] = useState(false);
  const [prefersDark, setPrefersDark] = useState(false);

  useEffect(() => {
    setSettings(readStoredAppSettings());
    setHydratedFromStorage(true);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const update = () => {
      setPrefersDark(media.matches);
    };
    update();
    media.addEventListener("change", update);
    return () => {
      media.removeEventListener("change", update);
    };
  }, []);

  useEffect(() => {
    applyDocumentSettings(settings, prefersDark);
  }, [prefersDark, settings]);

  useEffect(() => {
    if (!hydratedFromStorage) {
      return;
    }
    writeStoredAppSettings(settings);
  }, [hydratedFromStorage, settings]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const onStorage = (event: StorageEvent) => {
      if (event.key !== APP_SETTINGS_STORAGE_KEY) {
        return;
      }
      setSettings(readStoredAppSettings());
    };
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  const value = useMemo<AppSettingsContextValue>(
    () => ({
      settings,
      setTheme: (theme) => {
        setSettings((current) => ({ ...current, theme }));
      },
      setDevMode: (devMode) => {
        setSettings((current) => ({ ...current, devMode }));
      },
      setDensity: (density) => {
        setSettings((current) => ({ ...current, density }));
      },
      setReducedMotion: (reducedMotion) => {
        setSettings((current) => ({ ...current, reducedMotion }));
      },
      setEnrichmentSources: (enrichmentSources) => {
        setSettings((current) => ({ ...current, enrichmentSources }));
      },
      resetSettings: () => {
        setSettings(DEFAULT_APP_SETTINGS);
      }
    }),
    [settings]
  );

  return <AppSettingsContext.Provider value={value}>{children}</AppSettingsContext.Provider>;
}

export function useAppSettings(): AppSettingsContextValue {
  const context = useContext(AppSettingsContext);
  if (!context) {
    throw new Error("useAppSettings must be used within AppSettingsProvider.");
  }
  return context;
}

export function useIsDevMode(): boolean {
  return useAppSettings().settings.devMode;
}

export function DevOnly({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return useIsDevMode() ? <>{children}</> : null;
}

export function UserModeOnly({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return useIsDevMode() ? null : <>{children}</>;
}

export function WhenDevOff({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return useIsDevMode() ? null : <>{children}</>;
}
