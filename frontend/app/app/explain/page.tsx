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
          <CardTitle className="text-2xl tracking-tight">Record-level provenance and canonicalization context.</CardTitle>
          <CardDescription>
            Open a specific fact or relation explain page from entity tables, search results, or direct URL.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="rounded-lg border border-border bg-muted/30 p-4 text-sm">
            <p className="flex items-center gap-2 font-medium">
              <Info className="h-4 w-4 text-primary" />
              URL examples
            </p>
            <p className="mt-2">
              <code>/app/explain/facts/1</code> and <code>/app/explain/relations/1</code>
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button asChild>
              <Link href="/app/search">Go to Search</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/app/entities">Browse Entities</Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
