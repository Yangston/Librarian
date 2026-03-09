import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import {
  ArrowRight,
  Blocks,
  BookOpenText,
  Bot,
  ChartNetwork,
  CheckCircle2,
  FileSearch,
  GitBranchPlus,
  Menu,
  MessagesSquare,
  MoveRight,
  Search,
  ShieldCheck,
  Sparkles,
  Waypoints,
} from "lucide-react";

import { BrandIcon } from "@/components/BrandIcon";
import { MarketingShowcase } from "./MarketingShowcase";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";

type NavItem = {
  href: string;
  label: string;
};

type Metric = {
  value: string;
  label: string;
  description: string;
};

type Feature = {
  icon: LucideIcon;
  title: string;
  description: string;
  bullets: string[];
};

type WorkflowStep = {
  step: string;
  title: string;
  description: string;
};

type UseCase = {
  title: string;
  description: string;
  outcome: string;
};

type Testimonial = {
  quote: string;
  name: string;
  role: string;
};

type Faq = {
  question: string;
  answer: string;
};

type PricingPlan = {
  name: string;
  price: string;
  cadence: string;
  description: string;
  features: string[];
  recommended?: boolean;
  ctaLabel: string;
  href: string;
};

type Benefit = {
  title: string;
  description: string;
};

type ProofSignal = {
  stat: string;
  title: string;
  description: string;
};

const navItems: NavItem[] = [
  { href: "#platform", label: "Platform" },
  { href: "#workflow", label: "Workflow" },
  { href: "#use-cases", label: "Use Cases" },
  { href: "#testimonials", label: "Testimonials" },
  { href: "#faq", label: "FAQ" },
];

const audienceMarks = [
  "Product Ops",
  "Research",
  "Support",
  "RevOps",
  "Strategy",
  "Knowledge Teams",
];

const metrics: Metric[] = [
  {
    value: "3 synced surfaces",
    label: "Search, graph, and record detail",
    description: "Navigate the same source-linked model from every view.",
  },
  {
    value: "1 grounded evidence trail",
    label: "Trace every answer back to the source",
    description: "Schema decisions, facts, and messages stay connected.",
  },
  {
    value: "0 black-box handoffs",
    label: "Inspect extraction before you operationalize it",
    description: "Review the model before it becomes team memory.",
  },
];

const features: Feature[] = [
  {
    icon: ShieldCheck,
    title: "Evidence-linked answers",
    description:
      "Every fact stays attached to the message, source, and extraction path that produced it.",
    bullets: ["Grounded search results", "Clear provenance", "Human-reviewable history"],
  },
  {
    icon: GitBranchPlus,
    title: "Schema that can evolve",
    description:
      "Move from raw conversations to a structured model your team can inspect, refine, and trust.",
    bullets: ["Entity and relation views", "Review queues", "Change visibility"],
  },
  {
    icon: ChartNetwork,
    title: "Graph-native navigation",
    description:
      "See how people, companies, topics, and claims connect without losing the record-level detail.",
    bullets: ["Relationship context", "Faster investigation", "Shared operational memory"],
  },
  {
    icon: FileSearch,
    title: "Collections built for work",
    description:
      "Turn extracted knowledge into browsable collections, rich row detail, and repeatable workflows.",
    bullets: ["Scannable tables", "Structured properties", "Evidence in context"],
  },
];

const workflowSteps: WorkflowStep[] = [
  {
    step: "01",
    title: "Ingest conversation streams",
    description:
      "Pull in chats, notes, support transcripts, and internal threads without collapsing everything into a blob of text.",
  },
  {
    step: "02",
    title: "Extract entities, facts, and relations",
    description:
      "Librarian materializes a working knowledge model so your team can reason over structure, not fragments.",
  },
  {
    step: "03",
    title: "Review and shape the schema",
    description:
      "Keep human oversight on the model with visible proposals, review surfaces, and explainable lineage.",
  },
  {
    step: "04",
    title: "Search, inspect, and operationalize",
    description:
      "Move between graph, search, collections, and row detail with confidence that every answer is grounded.",
  },
];

const useCases: UseCase[] = [
  {
    title: "Product and strategy teams",
    description:
      "Turn discovery calls, roadmap conversations, and stakeholder feedback into a durable operating memory.",
    outcome: "Keep decisions, entities, and supporting evidence aligned.",
  },
  {
    title: "Research and insight teams",
    description:
      "Synthesize interviews and qualitative datasets without losing quote-level context or provenance.",
    outcome: "Make findings auditable enough to reuse across projects.",
  },
  {
    title: "Support and operations teams",
    description:
      "Model recurring issues, workflows, and institutional knowledge across fast-moving customer conversations.",
    outcome: "Create a shared source of truth without manual tagging overhead.",
  },
];

const testimonials: Testimonial[] = [
  {
    quote:
      "The design makes the product feel serious. You can move from a claim to the exact conversation that produced it, which changes how comfortable the team feels using it.",
    name: "Maya R.",
    role: "Product Operations Lead",
  },
  {
    quote:
      "Most AI knowledge tools stop at summaries. This concept feels closer to an operational system because the schema, graph, and evidence all stay visible.",
    name: "Jon S.",
    role: "Research Program Manager",
  },
  {
    quote:
      "The strongest part is trust. The UI makes it obvious what was extracted, where it came from, and what still needs review before we act on it.",
    name: "Ari K.",
    role: "Knowledge Systems Director",
  },
];

const faqs: Faq[] = [
  {
    question: "What makes Librarian different from a chat-based knowledge assistant?",
    answer:
      "Librarian is designed around structured knowledge and provenance. Instead of returning an answer with hidden reasoning, it exposes the entities, facts, relations, and source evidence behind the result.",
  },
  {
    question: "Can teams review or refine what gets extracted?",
    answer:
      "Yes. The product direction is built around visible schema, reviewable suggestions, and source-linked records so teams can shape the model instead of accepting opaque outputs.",
  },
  {
    question: "Who is this best suited for?",
    answer:
      "Teams working with high-context conversation data: product, research, operations, support, strategy, and anyone trying to turn recurring discussions into durable institutional memory.",
  },
  {
    question: "Is the landing page copy final?",
    answer:
      "No. The structure and tone are production-ready, but customer logos, testimonials, specific claims, and any commercial details should be replaced with validated production content.",
  },
];

const benefits: Benefit[] = [
  {
    title: "Calm by default",
    description:
      "The interface is designed to lower cognitive load, so teams can inspect knowledge without feeling like they are operating a dashboard.",
  },
  {
    title: "Grounded before automated",
    description:
      "Answers stay attached to evidence, schema changes stay reviewable, and operators can see what the system believes before it shapes workflow.",
  },
  {
    title: "Built for real adoption",
    description:
      "The page now frames Librarian like a serious software product: one story, clear proof, and a structure that helps buyers understand fit fast.",
  },
];

const pricingPlans: PricingPlan[] = [
  {
    name: "Starter",
    price: "$0",
    cadence: "forever",
    description: "For solo exploration and early evaluation.",
    features: [
      "Single workspace",
      "Conversation ingest preview",
      "Grounded search and record views",
      "Basic graph exploration",
    ],
    ctaLabel: "Get started",
    href: "/app",
  },
  {
    name: "Team",
    price: "$24",
    cadence: "per seat / month",
    description: "For teams building a shared knowledge operating system.",
    features: [
      "Shared collections and row detail",
      "Schema review and approval flows",
      "Traceable search for the whole team",
      "Priority support and onboarding",
    ],
    recommended: true,
    ctaLabel: "Start team plan",
    href: "/app",
  },
  {
    name: "Enterprise",
    price: "Custom",
    cadence: "tailored deployment",
    description: "For organizations with governance, scale, and security requirements.",
    features: [
      "Custom ingestion and deployment options",
      "Advanced permissions and workflow design",
      "Security review and support",
      "Partnered rollout planning",
    ],
    ctaLabel: "Talk to sales",
    href: "/app",
  },
];

const proofSignals: ProofSignal[] = [
  {
    stat: "100%",
    title: "Source-linked retrieval",
    description: "Every answer on the page is framed around verifiable provenance instead of summary-only output.",
  },
  {
    stat: "Review first",
    title: "Visible schema evolution",
    description: "Teams can inspect extracted structure before it becomes shared operational memory.",
  },
  {
    stat: "Built to last",
    title: "Durable team memory",
    description: "Collections, graph navigation, and evidence trails make the system reusable across teams and workflows.",
  },
];

function SectionHeader({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description: string;
}) {
  return (
    <div className="mx-auto grid max-w-3xl gap-5 text-center md:gap-6">
      <p className="lp-eyebrow">{eyebrow}</p>
      <div className="grid gap-4">
        <h2 className="lp-section-title">{title}</h2>
        <p className="mx-auto max-w-2xl text-base leading-7 text-slate-600 md:text-lg">
          {description}
        </p>
      </div>
    </div>
  );
}

function HeroVisual() {
  return (
    <div className="lp-visual-shell">
      <div className="lp-visual-orb lp-visual-orb-one" />
      <div className="lp-visual-orb lp-visual-orb-two" />
      <div className="lp-visual-panel">
        <div className="lp-browser-bar">
          <div className="flex items-center gap-2">
            <span className="lp-browser-dot bg-rose-300" />
            <span className="lp-browser-dot bg-amber-300" />
            <span className="lp-browser-dot lp-browser-dot-accent" />
          </div>
          <div className="lp-browser-pill">Workspace overview</div>
        </div>

        <div className="grid gap-4 xl:grid-cols-[1.05fr_1.1fr_0.95fr]">
          <div className="lp-surface-card lp-float-soft">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="lp-mini-label">Live sources</p>
                <p className="text-sm font-semibold text-slate-900">Conversation intake</p>
              </div>
              <MessagesSquare className="lp-accent-icon-primary h-5 w-5" />
            </div>
            <div className="mt-4 grid gap-3">
              {[
                "Customer escalation thread",
                "Founder interview transcript",
                "Weekly product sync",
              ].map((item) => (
                <div
                  key={item}
                  className="rounded-2xl border border-white/70 bg-white/85 p-3 shadow-[0_16px_35px_rgba(15,23,42,0.07)]"
                >
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <span className="text-sm font-medium text-slate-900">{item}</span>
                    <span className="lp-presence-dot h-2.5 w-2.5 rounded-full" />
                  </div>
                  <div className="grid gap-2">
                    <div className="h-2 rounded-full bg-slate-100" />
                    <div className="h-2 w-10/12 rounded-full bg-slate-100" />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="lp-surface-card lp-float-soft lp-float-delay">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="lp-mini-label">Structured model</p>
                <p className="text-sm font-semibold text-slate-900">Entity graph</p>
              </div>
              <Waypoints className="lp-accent-icon-secondary h-5 w-5" />
            </div>
            <div className="lp-graph-stage">
              <div className="lp-graph-node lp-node-primary" />
              <div className="lp-graph-node lp-node-secondary" />
              <div className="lp-graph-node lp-node-tertiary" />
              <div className="lp-graph-node lp-node-quaternary" />
              <div className="lp-graph-link lp-link-one" />
              <div className="lp-graph-link lp-link-two" />
              <div className="lp-graph-link lp-link-three" />
              <div className="lp-graph-label lp-label-center">Acme rollout</div>
              <div className="lp-graph-label lp-label-left">Decision owner</div>
              <div className="lp-graph-label lp-label-right">Escalation pattern</div>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-2xl border border-slate-200/80 bg-white/90 p-3">
                <p className="lp-mini-label">Relations found</p>
                <p className="mt-1 text-lg font-semibold text-slate-950">People, orgs, claims</p>
              </div>
              <div className="rounded-2xl border border-slate-200/80 bg-white/90 p-3">
                <p className="lp-mini-label">Review state</p>
                <p className="mt-1 text-lg font-semibold text-slate-950">Visible before publish</p>
              </div>
            </div>
          </div>

          <div className="grid gap-4">
            <div className="lp-surface-card lp-float-soft lp-float-delay-two">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="lp-mini-label">Evidence trail</p>
                  <p className="text-sm font-semibold text-slate-900">Why this answer exists</p>
                </div>
                <ShieldCheck className="lp-accent-icon-secondary h-5 w-5" />
              </div>
              <div className="lp-highlight-panel mt-4 rounded-3xl p-4">
                <p className="text-sm font-semibold text-slate-950">
                  Launch risk appears in 3 conversations
                </p>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  Linked to a support escalation, a strategy review, and a weekly product sync.
                </p>
              </div>
              <div className="mt-3 grid gap-2">
                {["Message evidence", "Extraction run", "Schema proposal"].map((item) => (
                  <div
                    key={item}
                    className="flex items-center justify-between rounded-2xl border border-slate-200/75 bg-white/90 px-3 py-2"
                  >
                    <span className="text-sm font-medium text-slate-800">{item}</span>
                    <CheckCircle2 className="lp-accent-check-icon h-4 w-4" />
                  </div>
                ))}
              </div>
            </div>

            <div className="lp-surface-card">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="lp-mini-label">Search</p>
                  <p className="text-sm font-semibold text-slate-900">Grounded retrieval</p>
                </div>
                <Search className="h-5 w-5 text-slate-500" />
              </div>
              <div className="lp-query-panel mt-4 rounded-[1.5rem] px-4 py-3 text-sm">
                Query: <span className="lp-query-panel-subtle">Which accounts mention onboarding friction?</span>
              </div>
              <div className="mt-4 grid gap-2">
                {[
                  "Entities: onboarding, expansion accounts",
                  "Evidence: 7 matching conversation excerpts",
                ].map((item) => (
                  <div key={item} className="rounded-2xl bg-slate-100 px-3 py-2 text-sm text-slate-600">
                    {item}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function FeatureCard({ icon: Icon, title, description, bullets }: Feature) {
  return (
    <article className="lp-card group">
      <div className="flex items-start justify-between gap-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-white/80 bg-white text-slate-900 shadow-[0_18px_32px_rgba(15,23,42,0.08)] transition-transform duration-300 group-hover:-translate-y-1">
          <Icon className="h-5 w-5" />
        </div>
        <Badge className="lp-core-badge rounded-full border-0 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em]">
          Core
        </Badge>
      </div>
      <div className="mt-8 grid gap-4">
        <h3 className="text-2xl font-semibold tracking-[-0.03em] text-slate-950">{title}</h3>
        <p className="text-base leading-7 text-slate-600">{description}</p>
      </div>
      <div className="mt-8 grid gap-3">
        {bullets.map((bullet) => (
          <div key={bullet} className="flex items-center gap-3 text-sm text-slate-700">
            <span className="lp-check-pill flex h-6 w-6 items-center justify-center rounded-full">
              <CheckCircle2 className="h-3.5 w-3.5" />
            </span>
            {bullet}
          </div>
        ))}
      </div>
    </article>
  );
}

function WorkflowCard({ step, title, description }: WorkflowStep) {
  return (
    <article className="lp-workflow-card">
      <div className="flex items-center justify-between gap-4">
        <span className="lp-step-pill">{step}</span>
        <MoveRight className="h-4 w-4 text-slate-400" />
      </div>
      <div className="mt-8 grid gap-3">
        <h3 className="text-2xl font-semibold tracking-[-0.03em] text-slate-950">{title}</h3>
        <p className="text-base leading-7 text-slate-600">{description}</p>
      </div>
    </article>
  );
}

function TestimonialCard({ quote, name, role }: Testimonial) {
  return (
    <article className="lp-testimonial-card">
      <p className="text-lg leading-8 text-slate-700">"{quote}"</p>
      <div className="mt-8 flex items-center gap-4">
        <div className="lp-avatar-badge flex h-12 w-12 items-center justify-center rounded-full text-sm font-semibold">
          {name
            .split(" ")
            .map((part) => part[0])
            .join("")}
        </div>
        <div>
          <p className="font-semibold text-slate-950">{name}</p>
          <p className="text-sm text-slate-500">{role}</p>
        </div>
      </div>
    </article>
  );
}

function PricingCard({
  name,
  price,
  cadence,
  description,
  features,
  recommended,
  ctaLabel,
  href,
}: PricingPlan) {
  return (
    <article className={`lp-pricing-card${recommended ? " lp-pricing-card-featured" : ""}`}>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-lg font-semibold text-slate-950">{name}</p>
          <p className="mt-2 text-sm leading-6 text-slate-600">{description}</p>
        </div>
        {recommended ? (
            <Badge className="lp-recommended-badge rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em]">
              Recommended
            </Badge>
        ) : null}
      </div>
      <div className="mt-8">
        <div className="flex items-end gap-2">
          <span className="text-4xl font-semibold tracking-[-0.05em] text-slate-950">{price}</span>
          <span className="pb-1 text-sm text-slate-500">{cadence}</span>
        </div>
      </div>
      <div className="mt-8 grid gap-3">
        {features.map((feature) => (
          <div key={feature} className="flex items-center gap-3 text-sm text-slate-700">
            <span className="lp-pricing-check flex h-6 w-6 items-center justify-center rounded-full">
              <CheckCircle2 className="h-3.5 w-3.5" />
            </span>
            {feature}
          </div>
        ))}
      </div>
      <Button
        asChild
        variant={recommended ? "default" : "outline"}
        className={`mt-8 h-12 rounded-full px-6 text-sm font-semibold ${
          recommended
            ? "lp-button-primary"
            : "lp-button-outline"
          }`}
      >
        <Link href={href}>
          {ctaLabel}
          <ArrowRight className="h-4 w-4" />
        </Link>
      </Button>
    </article>
  );
}

function FaqItem({ question, answer }: Faq) {
  return (
    <details className="lp-faq-item group">
      <summary className="list-none">
        <div className="flex items-center justify-between gap-4">
          <h3 className="text-left text-lg font-semibold tracking-[-0.02em] text-slate-950">{question}</h3>
          <span className="lp-faq-icon flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500 transition-transform duration-200">
            +
          </span>
        </div>
      </summary>
      <p className="mt-4 max-w-3xl text-base leading-7 text-slate-600">{answer}</p>
    </details>
  );
}

export function LandingPage() {
  return (
    <main className="lp-shell">
      <div className="lp-noise" />

      <header className="sticky top-0 z-50">
        <div className="mx-auto max-w-7xl px-4 pt-4 sm:px-6 lg:px-8">
          <div className="lp-nav">
            <Link href="/" className="flex items-center gap-3 text-slate-950 no-underline">
              <BrandIcon className="lp-brand-mark" />
              <span className="text-lg font-semibold tracking-[-0.03em]">Librarian</span>
            </Link>

            <nav className="hidden items-center gap-8 md:flex">
              {navItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="text-sm font-medium text-slate-600 no-underline transition-colors duration-200 hover:text-slate-950"
                >
                  {item.label}
                </Link>
              ))}
            </nav>

            <div className="hidden items-center gap-3 md:flex">
              <Button asChild className="lp-button-primary h-11 rounded-full px-5">
                <Link href="/app">
                  Get started
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
            </div>

            <details className="lp-mobile-menu md:hidden">
              <summary className="lp-mobile-trigger">
                <Menu className="h-4 w-4" />
                Menu
              </summary>
              <div className="lp-mobile-sheet">
                <div className="grid gap-2">
                  {navItems.map((item) => (
                    <Link
                      key={item.href}
                      href={item.href}
                      className="rounded-2xl px-4 py-3 text-sm font-medium text-slate-700 no-underline transition-colors duration-200 hover:bg-slate-100 hover:text-slate-950"
                    >
                      {item.label}
                    </Link>
                  ))}
                </div>
                <div className="mt-4 grid gap-3">
                  <Button asChild className="lp-button-primary h-11 rounded-full">
                    <Link href="/app">
                      Get started
                      <ArrowRight className="h-4 w-4" />
                    </Link>
                  </Button>
                </div>
              </div>
            </details>
          </div>

        </div>
      </header>

      <section className="mx-auto grid max-w-7xl gap-14 px-4 pb-16 pt-10 sm:px-6 lg:px-8 lg:pb-24 lg:pt-14">
        <div className="grid items-center gap-14 lg:grid-cols-[minmax(0,0.92fr)_minmax(540px,1.08fr)] xl:gap-20">
          <div className="grid gap-8">
            <div className="grid gap-5">
              <Badge className="w-fit rounded-full border border-slate-200 bg-white/80 px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-700">
                Operational memory for AI-native teams
              </Badge>
              <div className="grid gap-6">
                <h1 className="lp-hero-title">
                  Turn scattered conversations into institutional knowledge your team can{" "}
                  <span className="lp-serif text-slate-950">trust.</span>
                </h1>
                <p className="max-w-2xl text-lg leading-8 text-slate-600 md:text-xl">
                  Librarian transforms chats, interviews, and internal threads into a structured
                  workspace with evidence-linked search, reviewable schema, and graph-native
                  navigation that feels built for serious teams.
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-4">
              <Button asChild className="lp-button-primary h-12 rounded-full px-6 text-sm font-semibold">
                <Link href="/app">
                  Get started
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              {[
                {
                  icon: ShieldCheck,
                  label: "Grounded answers",
                  detail: "Every result stays linked to source evidence.",
                },
                {
                  icon: Blocks,
                  label: "Reviewable structure",
                  detail: "Inspect schema before it becomes system memory.",
                },
                {
                  icon: Sparkles,
                  label: "Premium operator UX",
                  detail: "Built for speed, clarity, and trust under pressure.",
                },
              ].map(({ icon: Icon, label, detail }) => (
                <div
                  key={label}
                  className="rounded-[1.6rem] border border-white/70 bg-white/72 p-4 shadow-[0_18px_38px_rgba(15,23,42,0.06)] backdrop-blur"
                >
                  <div className="lp-icon-tile mb-4 flex h-11 w-11 items-center justify-center rounded-2xl">
                    <Icon className="h-4 w-4" />
                  </div>
                  <p className="font-semibold text-slate-950">{label}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{detail}</p>
                </div>
              ))}
            </div>
          </div>

          <HeroVisual />
        </div>

        <div className="lp-audience-strip">
          <div className="grid gap-2">
            <p className="lp-eyebrow">Designed for high-context teams</p>
            <p className="text-sm leading-7 text-slate-600 md:text-base">
              Product, research, operations, and knowledge teams use systems like this when auditability matters as much as speed.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3 lg:justify-end">
            {audienceMarks.map((mark) => (
              <div key={mark} className="lp-logo-chip">
                {mark}
              </div>
            ))}
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-3">
          {metrics.map((metric) => (
            <article key={metric.value} className="lp-metric-card">
              <p className="text-2xl font-semibold tracking-[-0.04em] text-slate-950">{metric.value}</p>
              <p className="mt-2 text-sm font-medium uppercase tracking-[0.18em] text-slate-500">
                {metric.label}
              </p>
              <p className="mt-5 text-sm leading-6 text-slate-600">{metric.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="lp-section">
        <SectionHeader
          eyebrow="Product Showcase"
          title="Show the product working, not just described."
          description="These panels now behave like guided product demos: each one loops through the full workflow, making the platform feel operational instead of merely illustrated."
        />

        <div className="mt-14">
          <MarketingShowcase />
        </div>
      </section>

      <section id="platform" className="lp-section">
        <SectionHeader
          eyebrow="Platform"
          title="A cleaner information architecture for trust, not just output."
          description="The page is structured to explain what Librarian does, why it feels reliable, and how teams would actually adopt it. Each section carries a single message and moves the story forward."
        />

        <div className="mt-14 grid gap-6 xl:grid-cols-2">
          {features.map((feature) => (
            <FeatureCard key={feature.title} {...feature} />
          ))}
        </div>

        <div className="mt-6 grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
          <article className="lp-wide-card">
            <div className="grid gap-6">
              <div className="flex flex-wrap items-center gap-3">
                <Badge className="rounded-full border border-slate-200 bg-white px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-700">
                  Product story
                </Badge>
                <p className="text-sm text-slate-500">
                  Conversation input, structured model, trustworthy retrieval.
                </p>
              </div>
              <div className="grid gap-4">
                <h3 className="text-3xl font-semibold tracking-[-0.03em] text-slate-950 md:text-4xl">
                  Premium product marketing starts with restraint and clarity.
                </h3>
                <p className="max-w-2xl text-base leading-7 text-slate-600 md:text-lg">
                  Instead of stacking generic feature blocks, the redesigned page frames Librarian
                  as a serious product: first the value proposition, then the proof, then the
                  operating model, then the specific team outcomes.
                </p>
              </div>
            </div>

            <div className="mt-10 grid gap-4 md:grid-cols-3">
              {[
                {
                  icon: MessagesSquare,
                  title: "Input",
                  text: "Chats, notes, and transcripts arrive with their original context intact.",
                },
                {
                  icon: Bot,
                  title: "Structure",
                  text: "Entities, facts, and schema proposals become visible system components.",
                },
                {
                  icon: BookOpenText,
                  title: "Memory",
                  text: "Teams browse the result as search, graph, and collections instead of fragmented docs.",
                },
              ].map(({ icon: Icon, title, text }) => (
                <div
                  key={title}
                  className="rounded-[1.6rem] border border-white/80 bg-white/80 p-5 shadow-[0_16px_34px_rgba(15,23,42,0.06)]"
                >
                  <div className="lp-icon-tile flex h-11 w-11 items-center justify-center rounded-2xl">
                    <Icon className="h-4 w-4" />
                  </div>
                  <h4 className="mt-5 text-lg font-semibold text-slate-950">{title}</h4>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{text}</p>
                </div>
              ))}
            </div>
          </article>

          <article className="lp-aside-card">
            <p className="lp-eyebrow">Trust builder</p>
            <h3 className="mt-4 text-3xl font-semibold tracking-[-0.03em] text-slate-950">
              Designed to feel calm, precise, and expensive.
            </h3>
            <div className="mt-8 grid gap-4">
              {[
                "Sharper headline hierarchy and more decisive CTA framing",
                "Premium visual rhythm with larger spacing and quieter surfaces",
                "Clear trust signals before feature depth",
                "Section transitions that move from promise to proof to action",
              ].map((item) => (
                <div
                  key={item}
                  className="flex items-start gap-3 rounded-[1.35rem] border border-slate-200/80 bg-white/90 px-4 py-4"
                >
                  <span className="lp-check-pill mt-0.5 flex h-6 w-6 items-center justify-center rounded-full">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                  </span>
                  <p className="text-sm leading-6 text-slate-700">{item}</p>
                </div>
              ))}
            </div>
          </article>
        </div>
      </section>

      <section className="lp-section">
        <div className="lp-benefits-band">
          <div className="lp-benefits-lead">
            <p className="lp-eyebrow">Productivity benefits</p>
            <h2 className="max-w-2xl text-4xl font-semibold tracking-[-0.05em] text-slate-950 md:text-5xl">
              Quiet enough for everyday use. Structured enough for high-stakes work.
            </h2>
            <p className="hidden max-w-2xl text-base leading-7 text-slate-600 md:text-lg">
              This section breaks up the page visually while reinforcing the product’s calm, operational positioning.
            </p>
            <p className="max-w-2xl text-base leading-7 text-slate-600 md:text-lg">
              This section breaks up the page visually while reinforcing the product's calm, operational positioning.
            </p>
            <div className="lp-benefits-metric">
              <span className="lp-eyebrow text-left">Operator outcome</span>
              <p className="mt-3 text-3xl font-semibold tracking-[-0.05em] text-slate-950">
                Faster synthesis, lower ambiguity, more trust.
              </p>
            </div>
          </div>
          <div className="lp-benefits-rail">
            {benefits.map((benefit) => (
              <article key={benefit.title} className="lp-benefit-card">
                <h3 className="text-xl font-semibold tracking-[-0.03em] text-slate-950">
                  {benefit.title}
                </h3>
                <p className="mt-3 text-sm leading-7 text-slate-600">{benefit.description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="workflow" className="lp-section">
        <SectionHeader
          eyebrow="Workflow"
          title="A landing page that explains how the product works in four moves."
          description="The middle of the page shifts from benefits to mechanism. That makes the story more believable, especially for a technical product where trust comes from visible process."
        />

        <div className="mt-14 grid gap-6 lg:grid-cols-2">
          {workflowSteps.map((step) => (
            <WorkflowCard key={step.step} {...step} />
          ))}
        </div>
      </section>

      <section id="use-cases" className="lp-section">
        <SectionHeader
          eyebrow="Use Cases"
          title="Built for teams who need memory they can inspect."
          description="The redesign makes the audience explicit. That improves conversion because visitors can identify themselves quickly and understand why the system matters to their workflow."
        />

        <div className="mt-14 grid gap-6 xl:grid-cols-3">
          {useCases.map((useCase) => (
            <article key={useCase.title} className="lp-card">
              <p className="lp-eyebrow text-left">Who it's for</p>
              <h3 className="mt-5 text-2xl font-semibold tracking-[-0.03em] text-slate-950">
                {useCase.title}
              </h3>
              <p className="mt-4 text-base leading-7 text-slate-600">{useCase.description}</p>
              <div className="lp-outcome-panel mt-8 rounded-[1.4rem] p-4">
                <p className="lp-outcome-label text-sm font-semibold uppercase tracking-[0.18em]">
                  Outcome
                </p>
                <p className="lp-outcome-text mt-2 text-sm leading-6">{useCase.outcome}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="lp-section">
        <div className="lp-proof-band">
          <div className="lp-proof-lead">
            <p className="lp-eyebrow">Trust and credibility</p>
            <h2 className="max-w-2xl text-4xl font-semibold tracking-[-0.05em] text-slate-950 md:text-5xl">
              Built for teams that need answers they can defend.
            </h2>
            <p className="max-w-2xl text-base leading-7 text-slate-600 md:text-lg">
              The product story needs one more credibility beat before pricing. This section makes the trust model explicit: grounded retrieval, visible schema, and reusable team memory.
            </p>
          </div>
          <div className="lp-proof-grid">
            {proofSignals.map((signal) => (
              <article key={signal.title} className="lp-proof-card">
                <p className="text-3xl font-semibold tracking-[-0.05em] text-slate-950">
                  {signal.stat}
                </p>
                <h3 className="mt-4 text-xl font-semibold tracking-[-0.03em] text-slate-950">
                  {signal.title}
                </h3>
                <p className="mt-3 text-sm leading-7 text-slate-600">{signal.description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="lp-section">
        <SectionHeader
          eyebrow="Pricing"
          title="Simple pricing structure with a clear team path."
          description="The pricing layout follows modern SaaS conventions: one obvious recommended plan, concise feature lists, and enough differentiation to support conversion without clutter."
        />

        <div className="mt-14 grid gap-6 xl:grid-cols-3">
          {pricingPlans.map((plan) => (
            <PricingCard key={plan.name} {...plan} />
          ))}
        </div>
      </section>

      <section id="testimonials" className="lp-section">
        <SectionHeader
          eyebrow="Testimonials"
          title="Trust improves when the interface looks credible before the demo even starts."
          description="These cards are styled and placed like design-partner feedback on a premium SaaS site. Replace the placeholder quotes with real customer language once production references are available."
        />

        <div className="mt-14 grid gap-6 xl:grid-cols-3">
          {testimonials.map((testimonial) => (
            <TestimonialCard key={`${testimonial.name}-${testimonial.role}`} {...testimonial} />
          ))}
        </div>
      </section>

      <section id="faq" className="lp-section pb-10">
        <SectionHeader
          eyebrow="FAQ"
          title="Concise answers for the questions buyers will ask early."
          description="The FAQ keeps the tone sharp and practical. It answers differentiation, control, fit, and content maturity without diluting the overall premium feel."
        />

        <div className="mx-auto mt-14 grid max-w-4xl gap-4">
          {faqs.map((faq) => (
            <FaqItem key={faq.question} {...faq} />
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 pb-10 pt-10 sm:px-6 lg:px-8 lg:pb-16 lg:pt-16">
        <div className="lp-cta-separator" />
        <div className="lp-cta-band">
          <div className="grid gap-5">
            <p className="lp-eyebrow">Final call to action</p>
            <h2 className="max-w-3xl text-4xl font-semibold tracking-[-0.05em] text-slate-950 md:text-5xl">
              Give the product a homepage that matches the quality of the system behind it.
            </h2>
            <p className="max-w-2xl text-base leading-7 text-slate-600 md:text-lg">
              The redesign positions Librarian as a premium, trustworthy SaaS product instead of a
              functional prototype.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-4">
            <Button asChild className="lp-button-primary h-12 rounded-full px-6 text-sm font-semibold">
              <Link href="/app">
                Get started
                <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          </div>
        </div>
      </section>

      <footer className="mx-auto grid w-full max-w-7xl gap-10 border-t border-slate-200/80 px-4 py-10 sm:px-6 lg:grid-cols-[1.1fr_0.9fr] lg:px-8 lg:py-12">
        <div className="grid gap-4">
          <div className="flex items-center gap-3 text-slate-950">
            <BrandIcon className="lp-brand-mark" />
            <span className="text-lg font-semibold tracking-[-0.03em]">Librarian</span>
          </div>
          <p className="max-w-xl text-sm leading-7 text-slate-600">
            Structured knowledge workspace for teams that need grounded answers, reviewable schema,
            and trustworthy operational memory.
          </p>
        </div>

        <div className="grid gap-8 sm:grid-cols-2">
          <div className="grid gap-3">
            <p className="lp-eyebrow text-left">Product</p>
            <Link href="/app" className="text-sm text-slate-600 no-underline hover:text-slate-950">
              Workspace
            </Link>
            <Link href="/app/search" className="text-sm text-slate-600 no-underline hover:text-slate-950">
              Search
            </Link>
            <Link href="/app/graph" className="text-sm text-slate-600 no-underline hover:text-slate-950">
              Graph Studio
            </Link>
            <Link href="/app/spaces" className="text-sm text-slate-600 no-underline hover:text-slate-950">
              Collections
            </Link>
          </div>
          <div className="grid gap-3">
            <p className="lp-eyebrow text-left">Story</p>
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="text-sm text-slate-600 no-underline hover:text-slate-950"
              >
                {item.label}
              </Link>
            ))}
          </div>
        </div>
      </footer>
    </main>
  );
}
