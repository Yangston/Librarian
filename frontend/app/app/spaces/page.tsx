"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { getWorkspaceSpacesV3, type WorkspaceSpaceRead } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";

export default function SpacesIndexPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const spaces = await getWorkspaceSpacesV3();
        if (!active) {
          return;
        }
        const first = spaces[0];
        if (first) {
          router.replace(`/app/spaces/${first.slug}`);
          return;
        }
        setError("No spaces available yet.");
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load spaces.");
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [router]);

  return (
    <Card>
      <CardContent className="py-8 text-sm text-muted-foreground">
        {error ?? "Loading workspace..."}
      </CardContent>
    </Card>
  );
}
