import Link from "next/link";
import { Info } from "lucide-react";

import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../../components/ui/card";

export default function ExplainLandingPage() {
  return (
    <div className="space-y-4 routeFade">
      <Card className="border-border/80 bg-card/95">
        <CardHeader className="space-y-3">
          <Badge variant="secondary" className="w-fit">
            Explainability
          </Badge>
          <CardTitle className="text-2xl tracking-tight">Explain details now open inline from the workspace.</CardTitle>
          <CardDescription>
            Use the Explain side panel from Library, item detail, or Search to inspect evidence quickly.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-lg border border-border bg-muted/30 p-4 text-sm">
            <p className="flex items-center gap-2 font-medium">
              <Info className="h-4 w-4 text-primary" />
              Deep links still supported
            </p>
            <p className="mt-2">
              Open legacy deep links when needed: <code>/app/explain/facts/1</code> or{" "}
              <code>/app/explain/relations/1</code>
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button asChild>
              <Link href="/app/entities">Open Library</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/app/search">Search claims</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
