"use client";

import { useEffect, useMemo, useState } from "react";

import { useIsDevMode } from "@/components/AppSettingsProvider";
import {
  type PropertyCatalogRowV2,
  getPropertiesCatalogV2,
  updatePropertyCatalogV2
} from "@/lib/api";
import { formatTimestamp } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "@/components/ui/select";

export default function PropertiesPage() {
  const isDevMode = useIsDevMode();
  const [rows, setRows] = useState<PropertyCatalogRowV2[]>([]);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const payload = await getPropertiesCatalogV2({
          include_technical: isDevMode
        });
        if (!active) {
          return;
        }
        setRows(payload.items);
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load properties catalog.");
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
  }, [isDevMode]);

  const query = filter.trim().toLowerCase();
  const filteredRows = useMemo(() => {
    if (!query) {
      return rows;
    }
    return rows.filter((row) => `${row.display_label} ${row.kind} ${row.status}`.toLowerCase().includes(query));
  }, [query, rows]);

  const stableFields = filteredRows.filter((row) => row.kind === "field" && row.status === "stable");
  const emergingFields = filteredRows.filter((row) => row.kind === "field" && row.status === "emerging");
  const relationTypes = filteredRows.filter((row) => row.kind === "relation");

  async function updateStatus(propertyId: number, status: "stable" | "emerging" | "deprecated") {
    setSavingId(propertyId);
    setError(null);
    try {
      const updated = await updatePropertyCatalogV2(propertyId, {
        status,
        include_technical: isDevMode
      });
      setRows((current) => current.map((row) => (row.id === propertyId ? updated : row)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update property.");
    } finally {
      setSavingId(null);
    }
  }

  async function updateLabel(propertyId: number, nextLabel: string) {
    const label = nextLabel.trim();
    if (!label) {
      return;
    }
    setSavingId(propertyId);
    setError(null);
    try {
      const updated = await updatePropertyCatalogV2(propertyId, {
        display_label: label,
        include_technical: isDevMode
      });
      setRows((current) => current.map((row) => (row.id === propertyId ? updated : row)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to rename property.");
    } finally {
      setSavingId(null);
    }
  }

  function renderSection(title: string, description: string, sectionRows: PropertyCatalogRowV2[]) {
    return (
      <Card className="border-border/80 bg-card/95">
        <CardHeader className="pb-2">
          <CardTitle className="text-lg">{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {sectionRows.length === 0 ? (
            <p className="subtle">No entries.</p>
          ) : (
            sectionRows.map((row) => (
              <article key={row.id} className="rounded-lg border border-border/70 bg-background/60 p-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <Input
                    defaultValue={row.display_label}
                    className="max-w-[320px]"
                    onBlur={(event) => void updateLabel(row.id, event.target.value)}
                  />
                  <div className="flex items-center gap-2">
                    <Badge variant="outline">{row.kind}</Badge>
                    <Badge variant="secondary">{row.mention_count} mentions</Badge>
                  </div>
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <Select
                    value={row.status}
                    onValueChange={(value) =>
                      void updateStatus(row.id, value as "stable" | "emerging" | "deprecated")
                    }
                    disabled={savingId === row.id}
                  >
                    <SelectTrigger className="w-[180px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="stable">Stable</SelectItem>
                      <SelectItem value="emerging">Emerging</SelectItem>
                      <SelectItem value="deprecated">Deprecated</SelectItem>
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    Last seen {row.last_seen_at ? formatTimestamp(row.last_seen_at) : "never"}
                  </p>
                  {savingId === row.id ? <Button variant="outline">Saving...</Button> : null}
                </div>
                {isDevMode && row.technical_details ? (
                  <details className="mt-2">
                    <summary className="cursor-pointer text-xs text-muted-foreground">Technical details</summary>
                    <pre className="codeMini">{JSON.stringify(row.technical_details, null, 2)}</pre>
                  </details>
                ) : null}
              </article>
            ))
          )}
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="stackLg routeFade">
      <Card className="border-border/80 bg-card/95">
        <CardHeader className="pb-2">
          <CardTitle className="text-xl">Properties & Types</CardTitle>
          <CardDescription>
            Curate the labels your workspace uses, and keep emerging structure tidy over time.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Input
            placeholder="Filter properties..."
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
          />
        </CardContent>
      </Card>

      {error ? (
        <Card className="border-destructive/35 bg-destructive/5">
          <CardContent className="py-4 text-destructive">{error}</CardContent>
        </Card>
      ) : null}

      {loading ? (
        <Card>
          <CardContent className="py-6">Loading properties...</CardContent>
        </Card>
      ) : (
        <>
          {renderSection(
            "Stable Properties",
            "High-signal fields that are repeatedly used in your data.",
            stableFields
          )}
          {renderSection(
            "Emerging Suggestions",
            "New fields that may need consolidation, naming cleanup, or promotion.",
            emergingFields
          )}
          {renderSection(
            "Relation Types",
            "Relationship labels that connect items across your library.",
            relationTypes
          )}
        </>
      )}
    </div>
  );
}
