"use client";

import { useEffect, useMemo, useState } from "react";
import { ChartNetwork, FileSearch, MessagesSquare, type LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

type DemoPhaseConfig = {
  durations: number[];
  initialDelay?: number;
};

type GraphFocus = {
  title: string;
  stats: string[];
};

const CONVERSATION_TIMELINE: DemoPhaseConfig = {
  durations: [1000, 1100, 1000, 1000, 1400],
};

const GRAPH_TIMELINE: DemoPhaseConfig = {
  durations: [900, 900, 950, 950, 1400],
  initialDelay: 650,
};

const TRACE_TIMELINE: DemoPhaseConfig = {
  durations: [900, 800, 950, 900, 1400],
  initialDelay: 1200,
};

const GRAPH_FOCUS: GraphFocus[] = [
  {
    title: "Acme rollout",
    stats: ["Key owner: Product Ops", "Open dependencies: 2", "Source threads: 3"],
  },
  {
    title: "Onboarding friction",
    stats: ["Linked claims: 7", "Accounts affected: 4", "Latest evidence: Mar 2"],
  },
  {
    title: "RevOps escalation",
    stats: ["Related workflows: 3", "Confidence: reviewed", "Primary source: support sync"],
  },
];

function useReducedMotionPreference() {
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");

    function update() {
      setReducedMotion(document.documentElement.dataset.motion === "reduced" || mediaQuery.matches);
    }

    update();

    const handler = () => update();
    if (typeof mediaQuery.addEventListener === "function") {
      mediaQuery.addEventListener("change", handler);
      return () => mediaQuery.removeEventListener("change", handler);
    }

    mediaQuery.addListener(handler);
    return () => mediaQuery.removeListener(handler);
  }, []);

  return reducedMotion;
}

function useLoopedPhase({ durations, initialDelay = 0 }: DemoPhaseConfig) {
  const reducedMotion = useReducedMotionPreference();
  const [phase, setPhase] = useState(reducedMotion ? durations.length - 1 : 0);
  const durationsKey = useMemo(() => durations.join(","), [durations]);

  useEffect(() => {
    if (reducedMotion) {
      setPhase(durations.length - 1);
      return;
    }

    setPhase(0);

    let active = true;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;
    let phaseIndex = 0;

    const advance = () => {
      if (!active) {
        return;
      }

      phaseIndex = (phaseIndex + 1) % durations.length;
      setPhase(phaseIndex);
      timeoutId = setTimeout(advance, durations[phaseIndex]);
    };

    timeoutId = setTimeout(advance, durations[0] + initialDelay);

    return () => {
      active = false;
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, [durations, durations.length, durationsKey, initialDelay, reducedMotion]);

  return { phase, reducedMotion };
}

function ShowcaseCard({
  eyebrow,
  title,
  description,
  icon: Icon,
  children,
}: Readonly<{
  eyebrow: string;
  title: string;
  description: string;
  icon: LucideIcon;
  children: React.ReactNode;
}>) {
  return (
    <article className="lp-showcase-card">
      <div className="flex items-start justify-between gap-6">
        <div className="grid gap-4">
          <p className="lp-eyebrow text-left">{eyebrow}</p>
          <div className="grid gap-3">
            <h3 className="text-2xl font-semibold tracking-[-0.03em] text-slate-950 md:text-3xl">
              {title}
            </h3>
            <p className="max-w-2xl text-base leading-7 text-slate-600">{description}</p>
          </div>
        </div>
        <span className="lp-showcase-icon">
          <Icon className="h-5 w-5" />
        </span>
      </div>
      <div className="mt-8">{children}</div>
    </article>
  );
}

function ConversationStructuredDemo() {
  const { phase } = useLoopedPhase(CONVERSATION_TIMELINE);

  return (
    <div className="lp-flow-stage" data-phase={phase}>
      <div className="lp-flow-grid">
        <div className="lp-flow-chat">
          {[
            "Greenleaf flagged onboarding confusion after the revised setup flow.",
            "Northstar mentioned the same handoff gap in this week's support review.",
            "Let's log RevOps as owner and track the shared onboarding theme.",
          ].map((message, index) => (
            <div
              key={message}
              className={cn(
                "lp-flow-message",
                index % 2 === 0 ? "lp-flow-message-user" : "lp-flow-message-system",
                phase >= index ? "is-visible" : "",
              )}
            >
              <p>{message}</p>
              {index === 0 ? (
                <div className={cn("lp-flow-highlight", phase >= 1 ? "is-visible" : "")}>
                  <span>Greenleaf</span>
                  <span>onboarding confusion</span>
                </div>
              ) : null}
              {index === 1 ? (
                <div className={cn("lp-flow-highlight", phase >= 1 ? "is-visible" : "")}>
                  <span>Northstar</span>
                  <span>handoff gap</span>
                </div>
              ) : null}
            </div>
          ))}

          <div className={cn("lp-flow-chips", phase >= 2 ? "is-visible" : "")}>
            <span className={cn("lp-flow-chip", phase >= 3 ? "is-landed" : "")}>Account: Greenleaf</span>
            <span className={cn("lp-flow-chip", phase >= 3 ? "is-landed" : "")}>Theme: onboarding</span>
            <span className={cn("lp-flow-chip", phase >= 3 ? "is-landed" : "")}>Owner: RevOps</span>
          </div>
        </div>

        <div className="lp-flow-table">
          <div className="lp-flow-table-head">
            <span>Account</span>
            <span>Issue</span>
            <span>Owner</span>
          </div>
          {[
            ["Greenleaf", "Onboarding confusion", "RevOps"],
            ["Northstar", "Setup handoff gap", "Support"],
            ["Acadia", "Renewal blocker", "CS"],
          ].map((row, index) => (
            <div
              key={row.join("-")}
              className={cn("lp-flow-table-row", phase >= 3 + Math.min(index, 1) ? "is-visible" : "")}
            >
              {row.map((cell) => (
                <span key={cell}>{cell}</span>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function GraphNavigationDemo() {
  const { phase } = useLoopedPhase(GRAPH_TIMELINE);
  const activeIndex = phase >= 4 ? 2 : phase >= 3 ? 1 : 0;
  const activeFocus = GRAPH_FOCUS[activeIndex];

  return (
    <div className="lp-graph-showcase" data-phase={phase}>
      <div className="lp-graph-canvas">
        <span className={cn("lp-graph-focus-ring", `focus-${activeIndex}`)} />
        <button className={cn("lp-graph-point lp-graph-point-main", phase >= 0 ? "is-visible" : "")}>
          Expansion risk
        </button>
        <button className={cn("lp-graph-point lp-graph-point-a", phase >= 1 ? "is-visible" : "", activeIndex === 0 ? "is-active" : "")}>
          Acme rollout
        </button>
        <button className={cn("lp-graph-point lp-graph-point-b", phase >= 1 ? "is-visible" : "", activeIndex === 1 ? "is-active" : "")}>
          Onboarding friction
        </button>
        <button className={cn("lp-graph-point lp-graph-point-c", phase >= 1 ? "is-visible" : "", activeIndex === 2 ? "is-active" : "")}>
          RevOps escalation
        </button>
        <button className={cn("lp-graph-point lp-graph-point-d", phase >= 1 ? "is-visible" : "")}>Q2 launch</button>
        <span className={cn("lp-graph-edge lp-graph-edge-a", phase >= 1 ? "is-visible" : "")} />
        <span className={cn("lp-graph-edge lp-graph-edge-b", phase >= 1 ? "is-visible" : "")} />
        <span className={cn("lp-graph-edge lp-graph-edge-c", phase >= 1 ? "is-visible" : "")} />
        <span className={cn("lp-graph-edge lp-graph-edge-d", phase >= 1 ? "is-visible" : "")} />
      </div>

      <div className="lp-graph-inspector">
        <p className="lp-mini-label">Live inspector</p>
        <h4 className="text-lg font-semibold text-slate-950">{activeFocus.title}</h4>
        <div className="grid gap-2">
          {activeFocus.stats.map((item) => (
            <div key={item} className="lp-graph-inspector-row">
              {item}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function RetrievalTraceabilityDemo() {
  const { phase } = useLoopedPhase(TRACE_TIMELINE);
  const query =
    phase === 0
      ? "What changed in onboarding conversations..."
      : "What changed in onboarding conversations after the pricing update?";

  return (
    <div className="lp-trace-showcase" data-phase={phase}>
      <div className="lp-trace-query">
        <div className="lp-trace-query-input">
          <span>{query}</span>
          <span className={cn("lp-trace-caret", phase <= 1 ? "is-visible" : "")} />
        </div>
        <div className={cn("lp-trace-status", phase >= 1 ? "is-visible" : "")}>
          Searching source-linked evidence
        </div>
      </div>

      <div className={cn("lp-trace-answer", phase >= 2 ? "is-visible" : "")}>
        <p className="lp-mini-label">Retrieved answer</p>
        <p className="mt-3 text-sm leading-7 text-slate-700">
          Setup confusion increased after the pricing update, primarily in mid-market accounts,
          and traces back to a revised handoff sequence between sales and onboarding.
        </p>
      </div>

      <div className="lp-trace-sources">
        {[
          "Support review · Mar 2 · 4 mentions",
          "Customer interview · Mar 4 · 2 direct quotes",
          "Weekly sync · Mar 6 · schema-confirmed relation",
        ].map((item, index) => (
          <div
            key={item}
            className={cn(
              "lp-trace-source",
              phase >= 3 + Math.min(index, 1) ? "is-visible" : "",
            )}
          >
            {item}
          </div>
        ))}
      </div>
    </div>
  );
}

export function MarketingShowcase() {
  return (
    <div className="grid gap-6">
      <ShowcaseCard
        eyebrow="Conversation to structure"
        title="Extract signal from messy conversation flow."
        description="A mock conversation now resolves into extracted entities and then lands in structured records, so the core transformation reads as a real workflow."
        icon={MessagesSquare}
      >
        <ConversationStructuredDemo />
      </ShowcaseCard>

      <div className="grid gap-6 xl:grid-cols-[1.08fr_0.92fr]">
        <ShowcaseCard
          eyebrow="Knowledge graph"
          title="Navigate relationships with context still attached."
          description="The graph shifts focus between connected entities and updates the inspector as if someone is actively exploring the network."
          icon={ChartNetwork}
        >
          <GraphNavigationDemo />
        </ShowcaseCard>

        <ShowcaseCard
          eyebrow="Retrieval and traceability"
          title="Surface the answer and the evidence behind it."
          description="Search plays through the full trust loop: query, retrieval, answer, and the source trail that explains where it came from."
          icon={FileSearch}
        >
          <RetrievalTraceabilityDemo />
        </ShowcaseCard>
      </div>
    </div>
  );
}
