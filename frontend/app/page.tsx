import Link from "next/link";
import { ArrowRight, ChartNetwork, Search, Sparkles } from "lucide-react";

import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";

export default function HomePage() {
  return (
    <div className="marketingPage">
      <header className="marketingHero space-y-4 rounded-2xl border border-border/80 bg-card/95 p-6 shadow-sm">
        <Badge variant="secondary" className="w-fit">
          Librarian
        </Badge>
        <h1 className="max-w-4xl text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">
          From chat logs to a transparent knowledge product.
        </h1>
        <p className="max-w-3xl text-base text-muted-foreground sm:text-lg">
          Librarian turns conversations into linked entities, facts, relations, and explainable provenance.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <Button asChild size="lg">
            <Link href="/app">
              Open Workspace
              <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
          <Button asChild variant="outline" size="lg">
            <Link href="/app/search">
              Explore Search
              <Search className="h-4 w-4" />
            </Link>
          </Button>
        </div>
      </header>

      <section className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xl">Structured by Default</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Entities, properties, and relationships are continuously materialized as data.
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xl">Explainable by Design</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Every fact and relation links back to source messages, extraction runs, and schema decisions.
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xl">Human Navigation</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Search, graph, schema, and record views stay synced across conversations.
          </CardContent>
        </Card>
      </section>

      <section className="panel marketingProof rounded-2xl border border-border/80 bg-card/95">
        <div className="space-y-2">
          <p className="eyebrow">Workflow</p>
          <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">
            Conversation to extraction to entity graph to explainability.
          </h2>
          <p className="text-muted-foreground">
            Ship with confidence by making the system inspectable at every layer, not hidden behind prompts.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button asChild>
            <Link href="/app/graph">
              <ChartNetwork className="h-4 w-4" />
              Launch Graph Studio
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link href="/app/chat">
              <Sparkles className="h-4 w-4" />
              Start New Chat
            </Link>
          </Button>
        </div>
      </section>
    </div>
  );
}
