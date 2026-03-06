"use client";

import { useEffect, useState } from "react";

import { useIsDevMode } from "@/components/AppSettingsProvider";
import {
  type UnifiedClaimExplainV2,
  getClaimExplainV2,
  getFactExplain,
  getRelationExplain
} from "@/lib/api";
import { formatTimestamp } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export type ExplainTarget = {
  claimIndexId?: number;
  claimKind?: "fact" | "relation";
  claimId?: number;
  title?: string;
};

export function ExplainSidePanel({
  open,
  target,
  onOpenChange
}: Readonly<{
  open: boolean;
  target: ExplainTarget | null;
  onOpenChange: (nextOpen: boolean) => void;
}>) {
  const isDevMode = useIsDevMode();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [payload, setPayload] = useState<UnifiedClaimExplainV2 | null>(null);

  useEffect(() => {
    if (!open || !target) {
      return;
    }
    const targetRef = target;
    let active = true;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        let data: UnifiedClaimExplainV2;
        if (targetRef.claimIndexId) {
          data = await getClaimExplainV2(targetRef.claimIndexId, {
            include_technical: isDevMode
          });
        } else if (targetRef.claimKind === "fact" && targetRef.claimId) {
          const legacy = await getFactExplain(targetRef.claimId);
          data = {
            claim_index_id: legacy.fact.id,
            claim_kind: "fact",
            claim_id: legacy.fact.id,
            title: `${legacy.fact.subject_entity_name} ${legacy.fact.predicate} ${legacy.fact.object_value}`,
            why_this_exists:
              "This fact was extracted from source messages and retained as a workspace claim.",
            evidence_snippets: legacy.snippets,
            source_messages: legacy.source_messages,
            canonicalization: legacy.schema_canonicalization,
            technical_details: isDevMode
              ? {
                  extractor_run_id: legacy.extractor_run_id,
                  extraction_metadata: legacy.extraction_metadata,
                  resolution_events: legacy.resolution_events
                }
              : null
          };
        } else if (targetRef.claimKind === "relation" && targetRef.claimId) {
          const legacy = await getRelationExplain(targetRef.claimId);
          data = {
            claim_index_id: legacy.relation.id,
            claim_kind: "relation",
            claim_id: legacy.relation.id,
            title: `${legacy.relation.from_entity_name} ${legacy.relation.relation_type} ${legacy.relation.to_entity_name}`,
            why_this_exists:
              "This relation was extracted from source messages and retained as a workspace claim.",
            evidence_snippets: legacy.snippets,
            source_messages: legacy.source_messages,
            canonicalization: legacy.schema_canonicalization,
            technical_details: isDevMode
              ? {
                  extractor_run_id: legacy.extractor_run_id,
                  extraction_metadata: legacy.extraction_metadata,
                  resolution_events: legacy.resolution_events,
                  qualifiers_json: legacy.relation.qualifiers_json
                }
              : null
          };
        } else {
          throw new Error("Invalid explain target.");
        }
        if (!active) {
          return;
        }
        setPayload(data);
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load explain details.");
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [isDevMode, open, target]);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-[560px] overflow-y-auto sm:max-w-[700px]">
        <SheetHeader>
          <SheetTitle>{payload?.title ?? target?.title ?? "Explain claim"}</SheetTitle>
          <SheetDescription>
            Why this exists, where it came from, and how it was normalized.
          </SheetDescription>
        </SheetHeader>
        {loading ? <p className="subtle mt-4">Loading explain details...</p> : null}
        {error ? <p className="errorText mt-4">{error}</p> : null}
        {!loading && !error && payload ? (
          <Tabs defaultValue="why" className="mt-4 space-y-3">
            <TabsList>
              <TabsTrigger value="why">Why this exists</TabsTrigger>
              <TabsTrigger value="evidence">Evidence snippets</TabsTrigger>
              <TabsTrigger value="sources">Source messages</TabsTrigger>
              {isDevMode ? <TabsTrigger value="technical">Canonicalization</TabsTrigger> : null}
            </TabsList>
            <TabsContent value="why" className="space-y-2">
              <p>{payload.why_this_exists}</p>
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">{payload.claim_kind}</Badge>
                <Badge variant="secondary">Claim #{payload.claim_id}</Badge>
              </div>
            </TabsContent>
            <TabsContent value="evidence" className="space-y-2">
              {payload.evidence_snippets.length === 0 ? (
                <p className="subtle">No snippets were captured.</p>
              ) : (
                <ul className="simpleList">
                  {payload.evidence_snippets.map((snippet, index) => (
                    <li key={`${payload.claim_index_id}-${index}`}>{snippet}</li>
                  ))}
                </ul>
              )}
            </TabsContent>
            <TabsContent value="sources" className="space-y-2">
              {payload.source_messages.length === 0 ? (
                <p className="subtle">No source messages linked.</p>
              ) : (
                <ul className="simpleList">
                  {payload.source_messages.map((message) => (
                    <li key={message.id}>
                      <p>
                        <strong>{message.role}</strong> · {formatTimestamp(message.timestamp)}
                      </p>
                      <p className="subtle">{message.content}</p>
                    </li>
                  ))}
                </ul>
              )}
            </TabsContent>
            {isDevMode ? (
              <TabsContent value="technical" className="space-y-3">
                <div>
                  <p className="font-medium">Canonicalization</p>
                  {payload.canonicalization ? (
                    <pre className="codeMini">{JSON.stringify(payload.canonicalization, null, 2)}</pre>
                  ) : (
                    <p className="subtle">No canonicalization metadata.</p>
                  )}
                </div>
                <div>
                  <p className="font-medium">Technical details</p>
                  <pre className="codeMini">{JSON.stringify(payload.technical_details ?? {}, null, 2)}</pre>
                </div>
              </TabsContent>
            ) : null}
          </Tabs>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}
