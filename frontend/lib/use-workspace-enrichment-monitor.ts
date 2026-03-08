"use client";

import { useEffect, useRef, useState } from "react";

import {
  getWorkspaceEnrichmentRunV3,
  type WorkspaceEnrichmentRunRead
} from "@/lib/api";

const AUTO_POLL_WINDOW_MS = 5 * 60 * 1000;
const POLL_INTERVAL_MS = 3 * 1000;

type UseWorkspaceEnrichmentMonitorOptions = {
  onCompleted?: (run: WorkspaceEnrichmentRunRead) => Promise<void> | void;
  onFailed?: (message: string, run: WorkspaceEnrichmentRunRead) => void;
};

function formatRunStatus(run: WorkspaceEnrichmentRunRead): string {
  if (run.status === "running") {
    if (run.stage === "workspace_sync") {
      return "Workspace sync running. Accepted conversation truth will appear first.";
    }
    if (run.stage === "value_enrichment") {
      return "Value enrichment running. Missing cells are being researched.";
    }
    if (run.stage === "relation_enrichment") {
      return "Graph enrichment running. Missing relations are being researched.";
    }
  }
  if (run.status === "queued") {
    return "Enrichment queued. Checking status in the background.";
  }
  if (run.status === "completed") {
    return "Enrichment completed.";
  }
  return run.error_message || "Enrichment failed.";
}

function isTerminalStatus(status: string): boolean {
  return status === "completed" || status === "failed";
}

export function useWorkspaceEnrichmentMonitor(options?: UseWorkspaceEnrichmentMonitorOptions) {
  const callbacksRef = useRef(options);
  const completedRunIdsRef = useRef<Set<number>>(new Set());
  const pollStartedAtRef = useRef<number | null>(null);

  const [run, setRun] = useState<WorkspaceEnrichmentRunRead | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [isStartingRun, setIsStartingRun] = useState(false);
  const [isPolling, setIsPolling] = useState(false);

  useEffect(() => {
    callbacksRef.current = options;
  }, [options]);

  useEffect(() => {
    if (!run || isTerminalStatus(run.status)) {
      setIsPolling(false);
      return;
    }

    let cancelled = false;
    const runId = run.id;
    const startedAt = pollStartedAtRef.current ?? Date.now();
    pollStartedAtRef.current = startedAt;
    setIsPolling(true);

    async function poll() {
      while (!cancelled) {
        const elapsedMs = Date.now() - startedAt;
        if (elapsedMs >= AUTO_POLL_WINDOW_MS) {
          setIsPolling(false);
          setStatusMessage("Enrichment is still running. Refresh status to check again.");
          return;
        }

        await new Promise((resolve) => window.setTimeout(resolve, POLL_INTERVAL_MS));
        if (cancelled) {
          return;
        }

        try {
          const nextRun = await getWorkspaceEnrichmentRunV3(runId);
          const isDone = await applyRunUpdate(nextRun);
          if (isDone) {
            return;
          }
        } catch (error) {
          if (!cancelled) {
            setIsPolling(false);
            setStatusMessage(error instanceof Error ? error.message : "Failed to refresh enrichment status.");
          }
          return;
        }
      }
    }

    async function applyRunUpdate(nextRun: WorkspaceEnrichmentRunRead): Promise<boolean> {
      setRun(nextRun);
      setStatusMessage(formatRunStatus(nextRun));

      if (nextRun.status === "completed") {
        setIsPolling(false);
        if (!completedRunIdsRef.current.has(nextRun.id)) {
          completedRunIdsRef.current.add(nextRun.id);
          await callbacksRef.current?.onCompleted?.(nextRun);
        }
        return true;
      }

      if (nextRun.status === "failed") {
        setIsPolling(false);
        callbacksRef.current?.onFailed?.(nextRun.error_message || "Enrichment failed.", nextRun);
        return true;
      }

      return false;
    }

    void poll();
    return () => {
      cancelled = true;
    };
  }, [run]);

  function beginMonitoring(nextRun: WorkspaceEnrichmentRunRead) {
    completedRunIdsRef.current.delete(nextRun.id);
    pollStartedAtRef.current = Date.now();
    setRun(nextRun);
    setStatusMessage(formatRunStatus(nextRun));
  }

  async function startRun(factory: () => Promise<WorkspaceEnrichmentRunRead>) {
    setIsStartingRun(true);
    try {
      const nextRun = await factory();
      beginMonitoring(nextRun);
      return nextRun;
    } finally {
      setIsStartingRun(false);
    }
  }

  async function refreshStatus() {
    if (!run) {
      return null;
    }
    const nextRun = await getWorkspaceEnrichmentRunV3(run.id);
    setRun(nextRun);
    setStatusMessage(formatRunStatus(nextRun));

    if (nextRun.status === "completed") {
      setIsPolling(false);
      if (!completedRunIdsRef.current.has(nextRun.id)) {
        completedRunIdsRef.current.add(nextRun.id);
        await callbacksRef.current?.onCompleted?.(nextRun);
      }
    } else if (nextRun.status === "failed") {
      setIsPolling(false);
      callbacksRef.current?.onFailed?.(nextRun.error_message || "Enrichment failed.", nextRun);
    }

    return nextRun;
  }

  function clearRun() {
    pollStartedAtRef.current = null;
    setRun(null);
    setStatusMessage(null);
    setIsPolling(false);
  }

  return {
    run,
    statusMessage,
    isStartingRun,
    isPolling,
    beginMonitoring,
    startRun,
    refreshStatus,
    clearRun
  };
}
