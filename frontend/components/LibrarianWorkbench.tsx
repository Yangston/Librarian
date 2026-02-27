"use client";

import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";

import {
  apiGet,
  apiPost,
  type ConversationSummaryData,
  type EntityGraphData,
  type EntityRead,
  type EntityMergeAuditRead,
  type FactTimelineItem,
  type ExtractionRunResult,
  type FactExplainData,
  type FactWithSubjectRead,
  type LiveChatTurnResult,
  type MessageRead,
  type MessagesIngestRequest,
  type PredicateRegistryEntryRead,
  type ResolutionEventRead,
  type RelationExplainData,
  type RelationWithEntitiesRead,
  type SemanticSearchData
} from "../lib/api";

type WorkbenchMode = "full" | "database" | "explain" | "live";
type InputMode = "json" | "live";

type ExplainSelection =
  | { kind: "fact"; data: FactExplainData }
  | { kind: "relation"; data: RelationExplainData }
  | null;

const DEMO_MESSAGES: MessagesIngestRequest = {
  messages: [
    {
      role: "user",
      content: "AAPL reported iPhone revenue strength and the stock rose 3.2% after the call.",
      timestamp: "2026-02-24T14:00:00Z"
    },
    {
      role: "assistant",
      content: "TSLA reported vehicle deliveries and shares moved -1.4% in late trading.",
      timestamp: "2026-02-24T14:01:00Z"
    },
    {
      role: "user",
      content: "Fed rate decision impacted NVDA as traders reassessed AI valuations.",
      timestamp: "2026-02-24T14:02:00Z"
    },
    {
      role: "assistant",
      content: "Supply chain disruption impacted Apple Inc. and management flagged margin pressure.",
      timestamp: "2026-02-24T14:03:00Z"
    },
    {
      role: "user",
      content: "Apple saw margin pressure while MSFT reported cloud revenue acceleration and AMZN gained 2.1%.",
      timestamp: "2026-02-24T14:04:00Z"
    }
  ]
};

const DEMO_DRAFT = JSON.stringify(DEMO_MESSAGES, null, 2);

function buildConversationId(): string {
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  return `stocks-demo-web-${stamp}`;
}

function formatTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) {
    return value;
  }
  return date.toLocaleString();
}

function parseDraftMessages(value: string): MessagesIngestRequest {
  let parsed: unknown;
  try {
    parsed = JSON.parse(value);
  } catch {
    throw new Error("Messages JSON is invalid.");
  }

  if (!parsed || typeof parsed !== "object" || !("messages" in parsed)) {
    throw new Error("Messages JSON must be an object with a `messages` array.");
  }

  const candidate = parsed as { messages?: unknown };
  if (!Array.isArray(candidate.messages) || candidate.messages.length === 0) {
    throw new Error("`messages` must be a non-empty array.");
  }

  return parsed as MessagesIngestRequest;
}

function parsePositiveId(value: string, label: string): number {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed < 1) {
    throw new Error(`${label} must be a positive integer.`);
  }
  return parsed;
}

function formatScore(value: number | null | undefined, digits = 2): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "-";
  }
  return value.toFixed(digits);
}

function isHorizontalRuleLine(value: string): boolean {
  return /^(?:-{3,}|\*{3,}|_{3,})$/.test(value.trim());
}

function isOrderedListLine(value: string): boolean {
  return /^\d+[.)]\s+/.test(value.trim());
}

function isMarkdownTableRowLine(value: string): boolean {
  const trimmed = value.trim();
  return trimmed.startsWith("|") && trimmed.endsWith("|") && trimmed.indexOf("|", 1) !== -1;
}

function parseMarkdownTableRow(value: string): string[] {
  const trimmed = value.trim();
  const inner = trimmed.replace(/^\|/, "").replace(/\|$/, "");
  return inner.split("|").map((cell) => cell.trim());
}

function isMarkdownTableSeparatorLine(value: string): boolean {
  const cells = parseMarkdownTableRow(value);
  return cells.length > 0 && cells.every((cell) => /^:?-{3,}:?$/.test(cell));
}

function expandCompressedTableLines(value: string): string {
  return value.replace(/(^\s*\|.*$)/gm, (line) => line.replace(/\|\s+(?=\|)/g, "|\n"));
}

function renderInlineMarkdown(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const tokenPattern =
    /(\[[^\]]+\]\((?:https?:\/\/|mailto:)[^)]+\)|\*\*[^*\n]+\*\*|~~[^~\n]+~~|\*[^*\n]+\*|`[^`\n]+`)/g;
  let lastIndex = 0;
  let tokenIndex = 0;

  for (const match of text.matchAll(tokenPattern)) {
    const matched = match[0];
    const start = match.index ?? 0;
    if (start > lastIndex) {
      nodes.push(text.slice(lastIndex, start));
    }
    if (matched.startsWith("[") && matched.includes("](") && matched.endsWith(")")) {
      const linkMatch = /^\[([^\]]+)\]\(((?:https?:\/\/|mailto:)[^)]+)\)$/.exec(matched);
      if (linkMatch) {
        nodes.push(
          <a
            key={`${keyPrefix}-link-${tokenIndex}`}
            className="messageLink"
            href={linkMatch[2]}
            target="_blank"
            rel="noreferrer noopener"
          >
            {linkMatch[1]}
          </a>
        );
      } else {
        nodes.push(matched);
      }
    } else if (matched.startsWith("**") && matched.endsWith("**")) {
      nodes.push(
        <strong key={`${keyPrefix}-b-${tokenIndex}`}>{matched.slice(2, -2)}</strong>
      );
    } else if (matched.startsWith("~~") && matched.endsWith("~~")) {
      nodes.push(<del key={`${keyPrefix}-s-${tokenIndex}`}>{matched.slice(2, -2)}</del>);
    } else if (matched.startsWith("*") && matched.endsWith("*")) {
      nodes.push(<em key={`${keyPrefix}-i-${tokenIndex}`}>{matched.slice(1, -1)}</em>);
    } else if (matched.startsWith("`") && matched.endsWith("`")) {
      nodes.push(<code key={`${keyPrefix}-c-${tokenIndex}`}>{matched.slice(1, -1)}</code>);
    } else {
      nodes.push(matched);
    }
    lastIndex = start + matched.length;
    tokenIndex += 1;
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  return nodes.length > 0 ? nodes : [text];
}

function renderFormattedMessage(content: string): ReactNode {
  const normalized = expandCompressedTableLines(content.replace(/\r\n?/g, "\n")).trim();
  if (!normalized) {
    return null;
  }

  const lines = normalized.split("\n");
  const blocks: ReactNode[] = [];
  let lineIndex = 0;
  let blockIndex = 0;

  while (lineIndex < lines.length) {
    const line = lines[lineIndex];
    const trimmed = line.trim();

    if (!trimmed) {
      lineIndex += 1;
      continue;
    }

    const headingMatch = /^(#{1,6})\s+(.+)$/.exec(trimmed);
    if (headingMatch) {
      const level = Math.min(headingMatch[1].length, 6);
      blocks.push(
        <div
          key={`h-${blockIndex}`}
          className={`messageHeading messageHeadingLevel${Math.min(level, 3)}`}
        >
          {renderInlineMarkdown(headingMatch[2], `h-${blockIndex}`)}
        </div>
      );
      blockIndex += 1;
      lineIndex += 1;
      continue;
    }

    if (/^```/.test(trimmed)) {
      const language = trimmed.replace(/^```/, "").trim();
      lineIndex += 1;
      const codeLines: string[] = [];
      while (lineIndex < lines.length && !/^```/.test(lines[lineIndex].trim())) {
        codeLines.push(lines[lineIndex]);
        lineIndex += 1;
      }
      if (lineIndex < lines.length && /^```/.test(lines[lineIndex].trim())) {
        lineIndex += 1;
      }
      blocks.push(
        <div key={`code-${blockIndex}`} className="messageCodeBlockWrap">
          {language ? <div className="messageCodeLang mono">{language}</div> : null}
          <pre className="messageCodeBlock mono">
            <code>{codeLines.join("\n")}</code>
          </pre>
        </div>
      );
      blockIndex += 1;
      continue;
    }

    if (isHorizontalRuleLine(trimmed)) {
      blocks.push(<hr key={`hr-${blockIndex}`} className="messageRule" />);
      blockIndex += 1;
      lineIndex += 1;
      continue;
    }

    if (isMarkdownTableRowLine(trimmed)) {
      const headerLine = trimmed;
      const separatorCandidate = lines[lineIndex + 1]?.trim() ?? "";
      if (isMarkdownTableRowLine(separatorCandidate) && isMarkdownTableSeparatorLine(separatorCandidate)) {
        const headers = parseMarkdownTableRow(headerLine);
        lineIndex += 2;
        const rows: string[][] = [];
        while (lineIndex < lines.length) {
          const rowCandidate = lines[lineIndex].trim();
          if (!rowCandidate) {
            lineIndex += 1;
            break;
          }
          if (!isMarkdownTableRowLine(rowCandidate)) {
            break;
          }
          rows.push(parseMarkdownTableRow(rowCandidate));
          lineIndex += 1;
        }
        blocks.push(
          <div key={`table-${blockIndex}`} className="messageTableWrap">
            <table className="messageMarkdownTable">
              <thead>
                <tr>
                  {headers.map((header, columnIndex) => (
                    <th key={`th-${blockIndex}-${columnIndex}`}>
                      {renderInlineMarkdown(header, `th-${blockIndex}-${columnIndex}`)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, rowIndex) => (
                  <tr key={`tr-${blockIndex}-${rowIndex}`}>
                    {headers.map((_, columnIndex) => (
                      <td key={`td-${blockIndex}-${rowIndex}-${columnIndex}`}>
                        {renderInlineMarkdown(row[columnIndex] ?? "", `td-${blockIndex}-${rowIndex}-${columnIndex}`)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
        blockIndex += 1;
        continue;
      }
    }

    if (/^[-*]\s+/.test(trimmed)) {
      const items: string[] = [];
      while (lineIndex < lines.length) {
        const candidate = lines[lineIndex].trim();
        if (!candidate) {
          lineIndex += 1;
          break;
        }
        const bulletMatch = /^[-*]\s+(.+)$/.exec(candidate);
        if (!bulletMatch) {
          break;
        }
        items.push(bulletMatch[1]);
        lineIndex += 1;
      }
      blocks.push(
        <ul key={`ul-${blockIndex}`} className="messageMarkdownList">
          {items.map((item, itemIndex) => (
            <li key={`ul-${blockIndex}-${itemIndex}`}>
              {renderInlineMarkdown(item, `ul-${blockIndex}-${itemIndex}`)}
            </li>
          ))}
        </ul>
      );
      blockIndex += 1;
      continue;
    }

    if (isOrderedListLine(trimmed)) {
      const items: string[] = [];
      while (lineIndex < lines.length) {
        const candidate = lines[lineIndex].trim();
        if (!candidate) {
          lineIndex += 1;
          break;
        }
        const numberedMatch = /^\d+[.)]\s+(.+)$/.exec(candidate);
        if (!numberedMatch) {
          break;
        }
        items.push(numberedMatch[1]);
        lineIndex += 1;
      }
      blocks.push(
        <ol key={`ol-${blockIndex}`} className="messageMarkdownList messageMarkdownOrderedList">
          {items.map((item, itemIndex) => (
            <li key={`ol-${blockIndex}-${itemIndex}`}>
              {renderInlineMarkdown(item, `ol-${blockIndex}-${itemIndex}`)}
            </li>
          ))}
        </ol>
      );
      blockIndex += 1;
      continue;
    }

    if (/^>\s?/.test(trimmed)) {
      const quoteLines: string[] = [];
      while (lineIndex < lines.length) {
        const candidate = lines[lineIndex].trim();
        if (!candidate) {
          lineIndex += 1;
          break;
        }
        const quoteMatch = /^>\s?(.*)$/.exec(candidate);
        if (!quoteMatch) {
          break;
        }
        quoteLines.push(quoteMatch[1]);
        lineIndex += 1;
      }
      blocks.push(
        <blockquote key={`q-${blockIndex}`} className="messageQuote">
          <p className="messageParagraph">
            {renderInlineMarkdown(quoteLines.join(" "), `q-${blockIndex}`)}
          </p>
        </blockquote>
      );
      blockIndex += 1;
      continue;
    }

    const paragraphLines: string[] = [];
    while (lineIndex < lines.length) {
      const candidate = lines[lineIndex].trim();
      if (!candidate) {
        lineIndex += 1;
        break;
      }
      if (
        /^(#{1,6})\s+/.test(candidate) ||
        /^[-*]\s+/.test(candidate) ||
        isOrderedListLine(candidate) ||
        isHorizontalRuleLine(candidate) ||
        /^>\s?/.test(candidate) ||
        /^```/.test(candidate)
      ) {
        break;
      }
      if (isMarkdownTableRowLine(candidate)) {
        break;
      }
      paragraphLines.push(candidate);
      lineIndex += 1;
    }
    blocks.push(
      <p key={`p-${blockIndex}`} className="messageParagraph">
        {renderInlineMarkdown(paragraphLines.join(" "), `p-${blockIndex}`)}
      </p>
    );
    blockIndex += 1;
  }

  return <div className="messageContent">{blocks}</div>;
}

function mergeMessagesById(existing: MessageRead[], incoming: MessageRead[]): MessageRead[] {
  const map = new Map<number, MessageRead>();
  for (const message of existing) {
    map.set(message.id, message);
  }
  for (const message of incoming) {
    map.set(message.id, message);
  }
  return [...map.values()].sort((left, right) => {
    const leftTs = new Date(left.timestamp).valueOf();
    const rightTs = new Date(right.timestamp).valueOf();
    if (leftTs !== rightTs) {
      return leftTs - rightTs;
    }
    return left.id - right.id;
  });
}

export default function LibrarianWorkbench({
  mode = "full"
}: {
  mode?: WorkbenchMode;
}) {
  const [conversationId, setConversationId] = useState<string>(buildConversationId);
  const [messagesDraft, setMessagesDraft] = useState<string>(DEMO_DRAFT);
  const [inputMode, setInputMode] = useState<InputMode>("live");
  const [liveDraft, setLiveDraft] = useState<string>(
    "Give me a quick market read on Apple and AI supply chain risk."
  );
  const [liveAutoExtract, setLiveAutoExtract] = useState<boolean>(true);
  const [liveSystemPrompt, setLiveSystemPrompt] = useState<string>(
    "You are a stock research assistant helping test Librarian. Be concise, factual, and mention entities/events explicitly."
  );
  const [messages, setMessages] = useState<MessageRead[]>([]);
  const [entities, setEntities] = useState<EntityRead[]>([]);
  const [entityMerges, setEntityMerges] = useState<EntityMergeAuditRead[]>([]);
  const [resolutionEvents, setResolutionEvents] = useState<ResolutionEventRead[]>([]);
  const [predicateRegistryEntries, setPredicateRegistryEntries] = useState<PredicateRegistryEntryRead[]>([]);
  const [facts, setFacts] = useState<FactWithSubjectRead[]>([]);
  const [relations, setRelations] = useState<RelationWithEntitiesRead[]>([]);
  const [extractionResult, setExtractionResult] = useState<ExtractionRunResult | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>("Apple supply chain");
  const [searchConversationScoped, setSearchConversationScoped] = useState<boolean>(true);
  const [searchResult, setSearchResult] = useState<SemanticSearchData | null>(null);
  const [conversationSummary, setConversationSummary] = useState<ConversationSummaryData | null>(null);
  const [entityLookupId, setEntityLookupId] = useState<string>("");
  const [entityGraph, setEntityGraph] = useState<EntityGraphData | null>(null);
  const [entityTimeline, setEntityTimeline] = useState<FactTimelineItem[] | null>(null);
  const [lastLiveTurn, setLastLiveTurn] = useState<LiveChatTurnResult | null>(null);
  const [liveTurnPending, setLiveTurnPending] = useState<boolean>(false);
  const [pendingLiveUserText, setPendingLiveUserText] = useState<string | null>(null);
  const [backgroundExtractionActive, setBackgroundExtractionActive] = useState<boolean>(false);
  const [backgroundExtractionNote, setBackgroundExtractionNote] = useState<string | null>(null);
  const [explainSelection, setExplainSelection] = useState<ExplainSelection>(null);
  const [factExplainId, setFactExplainId] = useState<string>("");
  const [relationExplainId, setRelationExplainId] = useState<string>("");
  const [globalExplainLookup, setGlobalExplainLookup] = useState<boolean>(false);
  const [busyLabel, setBusyLabel] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string>("Ready.");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const extractionQueueRef = useRef<Promise<void>>(Promise.resolve());
  const chatTranscriptEndRef = useRef<HTMLDivElement | null>(null);

  const showJsonComposer = mode === "full" && inputMode === "json";
  const showLiveComposer = mode === "full" || mode === "live";
  const showDatabase = mode === "full" || mode === "database" || mode === "live";
  const showExplainTools = mode === "full" || mode === "explain" || mode === "live";

  useEffect(() => {
    chatTranscriptEndRef.current?.scrollIntoView({ block: "end" });
  }, [messages, pendingLiveUserText, liveTurnPending]);

  function requireConversationId(): string {
    const trimmed = conversationId.trim();
    if (!trimmed) {
      throw new Error("Conversation ID is required.");
    }
    return trimmed;
  }

  function conversationPath(id: string): string {
    return `/conversations/${encodeURIComponent(id)}`;
  }

  async function runTask(label: string, task: () => Promise<void>): Promise<void> {
    setBusyLabel(label);
    setErrorMessage(null);
    setStatusMessage(`${label}...`);
    try {
      await task();
      setStatusMessage(`${label} complete.`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unexpected error";
      setErrorMessage(message);
      setStatusMessage(`${label} failed.`);
    } finally {
      setBusyLabel(null);
    }
  }

  async function loadMessages(): Promise<void> {
    const id = requireConversationId();
    const result = await apiGet<MessageRead[]>(`${conversationPath(id)}/messages`);
    setMessages(result);
  }

  async function loadDatabase(): Promise<void> {
    const id = requireConversationId();
    const [entityRows, mergeRows, resolutionRows, factRows, relationRows, predicateRows] = await Promise.all([
      apiGet<EntityRead[]>(`${conversationPath(id)}/entities`),
      apiGet<EntityMergeAuditRead[]>(`${conversationPath(id)}/entity-merges`),
      apiGet<ResolutionEventRead[]>(`${conversationPath(id)}/resolution-events`),
      apiGet<FactWithSubjectRead[]>(`${conversationPath(id)}/facts`),
      apiGet<RelationWithEntitiesRead[]>(`${conversationPath(id)}/relations`),
      apiGet<PredicateRegistryEntryRead[]>("/schema/predicates")
    ]);
    setEntities(entityRows);
    setEntityMerges(mergeRows);
    setResolutionEvents(resolutionRows);
    setFacts(factRows);
    setRelations(relationRows);
    setPredicateRegistryEntries(predicateRows);
  }

  async function refreshWorkspaceViews(): Promise<void> {
    await loadMessages();
    if (showDatabase) {
      await loadDatabase();
    }
  }

  async function ingestDraftMessages(): Promise<void> {
    const id = requireConversationId();
    const payload = parseDraftMessages(messagesDraft);
    const created = await apiPost<MessageRead[]>(`${conversationPath(id)}/messages`, payload);
    setMessages(created);
    setLastLiveTurn(null);
    if (showDatabase) {
      await loadDatabase();
    }
  }

  async function runExtraction(): Promise<void> {
    const id = requireConversationId();
    const result = await apiPost<ExtractionRunResult>(`${conversationPath(id)}/extract`);
    setExtractionResult(result);
    if (showDatabase) {
      await loadDatabase();
    }
  }

  async function sendLiveChatTurn(): Promise<void> {
    const id = requireConversationId();
    const content = liveDraft.trim();
    if (!content) {
      throw new Error("Live chat message cannot be empty.");
    }
    setErrorMessage(null);
    setBusyLabel("Sending live chat turn");
    setStatusMessage("Assistant is responding...");
    setLiveTurnPending(true);
    setPendingLiveUserText(content);
    try {
      const result = await apiPost<LiveChatTurnResult>(`${conversationPath(id)}/chat/turn`, {
        content,
        auto_extract: false,
        system_prompt: liveSystemPrompt.trim() || null
      });

      setMessages((current) => mergeMessagesById(current, [result.user_message, result.assistant_message]));
      setLastLiveTurn({ ...result, extraction: null });
      setLiveDraft("");
      setStatusMessage("Assistant reply received.");

      if (liveAutoExtract) {
        queueBackgroundExtraction(id);
      } else if (showDatabase) {
        void loadDatabase().catch(() => undefined);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unexpected error";
      setErrorMessage(message);
      setStatusMessage("Live chat turn failed.");
    } finally {
      setBusyLabel(null);
      setLiveTurnPending(false);
      setPendingLiveUserText(null);
    }
  }

  function queueBackgroundExtraction(conversationIdToExtract: string): void {
    setBackgroundExtractionNote("Assistant replied. Updating structured memory in the background...");
    extractionQueueRef.current = extractionQueueRef.current
      .catch(() => undefined)
      .then(async () => {
        setBackgroundExtractionActive(true);
        try {
          const result = await apiPost<ExtractionRunResult>(
            `${conversationPath(conversationIdToExtract)}/extract`
          );
          setExtractionResult(result);
          if (showDatabase) {
            await loadDatabase();
          }
          setBackgroundExtractionNote(
            `Structured memory updated: ${result.entities_created} entities, ${result.facts_created} facts, ${result.relations_created} relations.`
          );
          setStatusMessage("Assistant reply received. Structured memory refreshed.");
        } catch (error) {
          const message = error instanceof Error ? error.message : "Unexpected error";
          setErrorMessage(message);
          setBackgroundExtractionNote("Background extraction failed.");
        } finally {
          setBackgroundExtractionActive(false);
        }
      });
  }

  async function runDemoFlow(): Promise<void> {
    const freshId = buildConversationId();
    setConversationId(freshId);
    setMessagesDraft(DEMO_DRAFT);

    const basePath = conversationPath(freshId);
    const created = await apiPost<MessageRead[]>(`${basePath}/messages`, DEMO_MESSAGES);
    const extract = await apiPost<ExtractionRunResult>(`${basePath}/extract`);
    const [entityRows, mergeRows, resolutionRows, factRows, relationRows, predicateRows] = await Promise.all([
      apiGet<EntityRead[]>(`${basePath}/entities`),
      apiGet<EntityMergeAuditRead[]>(`${basePath}/entity-merges`),
      apiGet<ResolutionEventRead[]>(`${basePath}/resolution-events`),
      apiGet<FactWithSubjectRead[]>(`${basePath}/facts`),
      apiGet<RelationWithEntitiesRead[]>(`${basePath}/relations`),
      apiGet<PredicateRegistryEntryRead[]>("/schema/predicates")
    ]);

    setMessages(created);
    setExtractionResult(extract);
    setEntities(entityRows);
    setEntityMerges(mergeRows);
    setResolutionEvents(resolutionRows);
    setFacts(factRows);
    setRelations(relationRows);
    setPredicateRegistryEntries(predicateRows);
    setConversationSummary(null);
    setSearchResult(null);
    setEntityGraph(null);
    setEntityTimeline(null);
    setEntityLookupId("");
    setExplainSelection(null);
    setFactExplainId("");
    setRelationExplainId("");
    setGlobalExplainLookup(false);
    setLastLiveTurn(null);
    setInputMode("live");
  }

  const canonicalEntities = entities.filter((entity) => entity.merged_into_id === null);
  const mergedEntities = entities.filter((entity) => entity.merged_into_id !== null);
  const factPredicateEntries = predicateRegistryEntries.filter(
    (entry) => entry.kind === "fact_predicate"
  );
  const relationTypeEntries = predicateRegistryEntries.filter(
    (entry) => entry.kind === "relation_type"
  );
  const displayedMessages = messages;
  const canSendLiveTurn = !liveTurnPending && conversationId.trim().length > 0;
  const conversationModeLabel =
    mode === "live"
      ? "Live Chat Test"
      : mode === "database"
        ? "Database Inspector"
        : mode === "explain"
          ? "Explainability Inspector"
          : "Unified Test Console";

  async function loadFactExplainById(factId: number): Promise<void> {
    const path = globalExplainLookup
      ? `/facts/${factId}/explain`
      : `${conversationPath(requireConversationId())}/facts/${factId}/explain`;
    const data = await apiGet<FactExplainData>(path);
    setExplainSelection({ kind: "fact", data });
    setFactExplainId(String(factId));
  }

  async function loadRelationExplainById(relationId: number): Promise<void> {
    const path = globalExplainLookup
      ? `/relations/${relationId}/explain`
      : `${conversationPath(requireConversationId())}/relations/${relationId}/explain`;
    const data = await apiGet<RelationExplainData>(path);
    setExplainSelection({ kind: "relation", data });
    setRelationExplainId(String(relationId));
  }

  async function runSemanticSearch(): Promise<void> {
    const query = searchQuery.trim();
    if (!query) {
      throw new Error("Search query is required.");
    }
    const params = new URLSearchParams();
    params.set("q", query);
    params.set("limit", "10");
    if (searchConversationScoped) {
      const scopedConversationId = requireConversationId();
      params.set("conversation_id", scopedConversationId);
    }
    const data = await apiGet<SemanticSearchData>(`/search?${params.toString()}`);
    setSearchResult(data);
  }

  async function loadConversationSummary(): Promise<void> {
    const id = requireConversationId();
    const data = await apiGet<ConversationSummaryData>(`${conversationPath(id)}/summary`);
    setConversationSummary(data);
  }

  async function loadEntityKnowledgeViews(entityId: number): Promise<void> {
    const [graphData, timelineData] = await Promise.all([
      apiGet<EntityGraphData>(`/entities/${entityId}/graph`),
      apiGet<FactTimelineItem[]>(`/entities/${entityId}/timeline`)
    ]);
    setEntityGraph(graphData);
    setEntityTimeline(timelineData);
    setEntityLookupId(String(entityId));
  }

  return (
    <main className="grid">
      <section className="panel grid">
        <div className="sectionHead">
          <h2 style={{ margin: 0 }}>{conversationModeLabel}</h2>
          <p className="muted" style={{ margin: 0 }}>
            Test Librarian with either batch JSON ingestion or live GPT chat turns, then inspect
            structured outputs and traceability without leaving the UI.
          </p>
        </div>

        {mode === "full" ? (
          <div className="modeSwitch" role="tablist" aria-label="Testing mode">
            <button
              className={`button ghost segmented ${inputMode === "live" ? "active" : ""}`}
              type="button"
              onClick={() => setInputMode("live")}
              disabled={busyLabel !== null}
            >
              Live Chat Test
            </button>
            <button
              className={`button ghost segmented ${inputMode === "json" ? "active" : ""}`}
              type="button"
              onClick={() => setInputMode("json")}
              disabled={busyLabel !== null}
            >
              JSON Batch Test
            </button>
          </div>
        ) : null}

        <div className="toolbar">
          <label className="field grow">
            <span className="label">Conversation ID</span>
            <input
              className="input mono"
              value={conversationId}
              onChange={(event) => setConversationId(event.target.value)}
              placeholder="stocks-demo-web-001"
            />
          </label>

          <button
            className="button ghost"
            type="button"
            disabled={busyLabel !== null}
            onClick={() => setConversationId(buildConversationId())}
          >
            New ID
          </button>

          <button
            className="button ghost"
            type="button"
            disabled={busyLabel !== null}
            onClick={() => {
              void runTask("Refresh workspace", refreshWorkspaceViews);
            }}
          >
            Refresh Workspace
          </button>

          {mode === "full" ? (
            <button
              className="button"
              type="button"
              disabled={busyLabel !== null}
              onClick={() => {
                void runTask("Run demo flow", runDemoFlow);
              }}
            >
              Run Demo Flow
            </button>
          ) : null}
        </div>

        <div className="toolbar">
          {showJsonComposer ? (
            <>
              <button
                className="button ghost"
                type="button"
                disabled={busyLabel !== null}
                onClick={() => setMessagesDraft(DEMO_DRAFT)}
              >
                Load Demo JSON
              </button>
              <button
                className="button"
                type="button"
                disabled={busyLabel !== null}
                onClick={() => {
                  void runTask("Ingest messages", ingestDraftMessages);
                }}
              >
                POST Messages
              </button>
              <button
                className="button"
                type="button"
                disabled={busyLabel !== null}
                onClick={() => {
                  void runTask("Run extraction", runExtraction);
                }}
              >
                POST Extract
              </button>
            </>
          ) : null}

          {showLiveComposer ? (
            <span className="pill neutral">
              {mode === "live" || inputMode === "live"
                ? "Live chat mode ready"
                : "Live chat available on /live or in full mode"}
            </span>
          ) : null}

          <button
            className="button ghost"
            type="button"
            disabled={busyLabel !== null}
            onClick={() => {
              void runTask("Load messages", loadMessages);
            }}
          >
            GET Messages
          </button>

          {showDatabase ? (
            <button
              className="button ghost"
              type="button"
              disabled={busyLabel !== null}
              onClick={() => {
                void runTask("Load database views", loadDatabase);
              }}
            >
              GET Structured Views
            </button>
          ) : null}
        </div>

        <div className="statusRow">
          <span className={`pill ${busyLabel ? "busy" : "ok"}`}>{busyLabel ?? "Idle"}</span>
          <span className="mono muted">{statusMessage}</span>
          {errorMessage ? <span className="errorText">{errorMessage}</span> : null}
        </div>

        {backgroundExtractionNote ? (
          <div className={`callout ${backgroundExtractionActive ? "calloutBusy" : ""}`}>
            <div className="calloutTitle">Background extraction</div>
            <div className="mono muted">{backgroundExtractionNote}</div>
          </div>
        ) : null}

        {lastLiveTurn ? (
          <div className="callout">
            <div className="calloutTitle">Last live chat turn</div>
            <div className="mono muted">
              user #{lastLiveTurn.user_message.id}
              {" -> "}
              assistant #{lastLiveTurn.assistant_message.id}
              {backgroundExtractionActive
                ? " - parsing structured data in background"
                : liveAutoExtract
                  ? " - background parsing enabled"
                  : " - background parsing disabled"}
            </div>
          </div>
        ) : null}

        {extractionResult ? (
          <div className="stats">
            <div className="stat">
              <span className="statLabel">Extractor Run</span>
              <strong>{extractionResult.extractor_run_id ?? "-"}</strong>
            </div>
            <div className="stat">
              <span className="statLabel">Messages Processed</span>
              <strong>{extractionResult.messages_processed}</strong>
            </div>
            <div className="stat">
              <span className="statLabel">Entities</span>
              <strong>{extractionResult.entities_created}</strong>
            </div>
            <div className="stat">
              <span className="statLabel">Facts</span>
              <strong>{extractionResult.facts_created}</strong>
            </div>
            <div className="stat">
              <span className="statLabel">Relations</span>
              <strong>{extractionResult.relations_created}</strong>
            </div>
          </div>
        ) : null}
      </section>

      {showJsonComposer ? (
        <section className="panel grid">
          <div className="sectionHead">
            <h2 style={{ margin: 0 }}>JSON Batch Input</h2>
            <p className="muted" style={{ margin: 0 }}>
              Paste a batch of conversation messages and submit in one request.
            </p>
          </div>
          <label className="field">
            <span className="label">Messages JSON Payload</span>
            <textarea
              className="textarea mono"
              value={messagesDraft}
              onChange={(event) => setMessagesDraft(event.target.value)}
              rows={14}
              spellCheck={false}
            />
          </label>
        </section>
      ) : null}

      {showLiveComposer ? (
        <section className="panel grid liveSettingsPanel">
          <div className="sectionHead">
            <h2 style={{ margin: 0 }}>Live Chat Settings</h2>
            <p className="muted" style={{ margin: 0 }}>
              Configure the GPT test persona and background extraction behavior. The conversation
              happens in the chatroom below.
            </p>
          </div>

          <div className="grid two">
            <label className="field">
              <span className="label">System Prompt (Optional)</span>
              <textarea
                className="textarea"
                value={liveSystemPrompt}
                onChange={(event) => setLiveSystemPrompt(event.target.value)}
                rows={4}
              />
            </label>

            <div className="panel inset grid">
              <div className="sectionHead">
                <h3 className="subhead" style={{ margin: 0 }}>
                  Turn Processing
                </h3>
                <p className="muted" style={{ margin: 0 }}>
                  Fast mode returns the assistant reply first, then parses entities/facts/relations
                  in the background.
                </p>
              </div>
              <label className="toggleRow">
                <input
                  type="checkbox"
                  checked={liveAutoExtract}
                  onChange={(event) => setLiveAutoExtract(event.target.checked)}
                  disabled={busyLabel !== null}
                />
                <span>Auto-parse structured data after each live reply (background)</span>
              </label>
              <div className="mono muted">
                Endpoint: <code>/conversations/:id/chat/turn</code>
              </div>
            </div>
          </div>
        </section>
      ) : null}

      {showLiveComposer || messages.length > 0 ? (
        <section className="panel grid chatroomPanel">
          <div className="sectionHead">
            <h2 style={{ margin: 0 }}>
              {showLiveComposer ? "Live Chatroom" : "Messages"} ({messages.length})
            </h2>
            <p className="muted" style={{ margin: 0 }}>
              {showLiveComposer
                ? "Back-and-forth chat transcript. New assistant replies appear first; structured parsing updates afterward."
                : "Stored conversation messages ordered by timestamp and ID. Live chat and batch testing both feed the same message store."}
            </p>
          </div>

          <div className={`chatTranscript ${showLiveComposer ? "chatMode" : ""}`}>
            {displayedMessages.length === 0 && !pendingLiveUserText ? (
              <div className="emptyChatState">
                <p style={{ margin: 0 }}>
                  No messages yet. Start with a live prompt or load messages from a JSON batch.
                </p>
              </div>
            ) : null}

            {displayedMessages.map((message) => (
              <article
                className={`chatBubbleRow ${message.role === "user" ? "fromUser" : "fromAssistant"}`}
                key={message.id}
              >
                <div
                  className={`messageCard chatBubble ${message.role === "user" ? "userMessage" : "assistantMessage"}`}
                >
                  <div className="messageMeta">
                    <span className="pill neutral mono">#{message.id}</span>
                    <span className="pill role">{message.role}</span>
                    <span className="mono muted">{formatTimestamp(message.timestamp)}</span>
                  </div>
                  {renderFormattedMessage(message.content)}
                </div>
              </article>
            ))}

            {pendingLiveUserText ? (
              <article className="chatBubbleRow fromUser">
                <div className="messageCard chatBubble userMessage pendingBubble">
                  <div className="messageMeta">
                    <span className="pill neutral mono">pending</span>
                    <span className="pill role">user</span>
                  </div>
                  <p style={{ margin: 0 }}>{pendingLiveUserText}</p>
                </div>
              </article>
            ) : null}

            {liveTurnPending ? (
              <article className="chatBubbleRow fromAssistant">
                <div className="messageCard chatBubble assistantMessage pendingBubble">
                  <div className="messageMeta">
                    <span className="pill neutral mono">pending</span>
                    <span className="pill role">assistant</span>
                  </div>
                  <p style={{ margin: 0 }}>Thinking...</p>
                </div>
              </article>
            ) : null}
            <div ref={chatTranscriptEndRef} />
          </div>

          {showLiveComposer ? (
            <div className="chatComposerShell">
              <label className="field">
                <span className="label">Your Message</span>
                <textarea
                  className="textarea chatComposerInput"
                  value={liveDraft}
                  onChange={(event) => setLiveDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      if (canSendLiveTurn) {
                        void sendLiveChatTurn();
                      }
                    }
                  }}
                  rows={3}
                  placeholder="Ask GPT about companies, events, or market impacts to generate live test data..."
                />
              </label>
              <div className="toolbar">
                <button
                  className="button"
                  type="button"
                  disabled={!canSendLiveTurn}
                  onClick={() => {
                    void sendLiveChatTurn();
                  }}
                >
                  {liveTurnPending ? "Sending..." : "Send"}
                </button>
                <button
                  className="button ghost"
                  type="button"
                  disabled={busyLabel !== null || liveTurnPending}
                  onClick={() => {
                    setLiveDraft(
                      "Compare AAPL and NVDA exposure to AI supply chain disruptions this quarter."
                    );
                  }}
                >
                  Load Prompt
                </button>
                <button
                  className="button ghost"
                  type="button"
                  disabled={busyLabel !== null || liveTurnPending}
                  onClick={() => {
                    void runTask("Manual extraction", runExtraction);
                  }}
                >
                  Parse Now
                </button>
              </div>
            </div>
          ) : null}
        </section>
      ) : null}

      {showDatabase ? (
        <section className="panel grid">
          <div className="sectionHead">
            <h2 style={{ margin: 0 }}>Structured Memory Inspector</h2>
            <p className="muted" style={{ margin: 0 }}>
              Canonical entities, merge audits, facts, and relations generated from the current
              conversation.
            </p>
          </div>

          <div className="grid threeStats">
            <div className="miniCard">
              <div className="miniLabel">Entities</div>
              <div className="miniValue">{entities.length}</div>
            </div>
            <div className="miniCard">
              <div className="miniLabel">Canonical / Merged</div>
              <div className="miniValue">
                {canonicalEntities.length} / {mergedEntities.length}
              </div>
            </div>
            <div className="miniCard">
              <div className="miniLabel">Merge Audits</div>
              <div className="miniValue">{entityMerges.length}</div>
            </div>
          </div>

          <div className="grid threeStats">
            <div className="miniCard">
              <div className="miniLabel">Facts</div>
              <div className="miniValue">{facts.length}</div>
            </div>
            <div className="miniCard">
              <div className="miniLabel">Relations</div>
              <div className="miniValue">{relations.length}</div>
            </div>
            <div className="miniCard">
              <div className="miniLabel">Resolution Events</div>
              <div className="miniValue">{resolutionEvents.length}</div>
            </div>
          </div>

          <div className="grid threeStats">
            <div className="miniCard">
              <div className="miniLabel">Resolver</div>
              <div className="miniValue">
                {canonicalEntities[0]?.resolver_version ?? entities[0]?.resolver_version ?? "-"}
              </div>
            </div>
            <div className="miniCard">
              <div className="miniLabel">Predicate Registry</div>
              <div className="miniValue">{predicateRegistryEntries.length}</div>
            </div>
            <div className="miniCard">
              <div className="miniLabel">Fact Predicates</div>
              <div className="miniValue">{factPredicateEntries.length}</div>
            </div>
            <div className="miniCard">
              <div className="miniLabel">Relation Types</div>
              <div className="miniValue">{relationTypeEntries.length}</div>
            </div>
          </div>

          <div className="tableWrap">
            <table className="table mono">
              <caption>Predicate Registry (Global Schema Vocabulary)</caption>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Kind</th>
                  <th>Canonical</th>
                  <th>Aliases</th>
                  <th>Frequency</th>
                  <th>Last Seen</th>
                </tr>
              </thead>
              <tbody>
                {predicateRegistryEntries.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="emptyCell">
                      No predicates registered yet. Run extraction to build the schema vocabulary.
                    </td>
                  </tr>
                ) : (
                  predicateRegistryEntries.map((entry) => (
                    <tr key={`${entry.kind}-${entry.id}`}>
                      <td>{entry.id}</td>
                      <td>{entry.kind}</td>
                      <td>{entry.predicate}</td>
                      <td>{entry.aliases_json.join(", ") || "-"}</td>
                      <td>{entry.frequency}</td>
                      <td>{formatTimestamp(entry.last_seen_at)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="tableWrap">
            <table className="table mono">
              <caption>Entities</caption>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Name</th>
                  <th>Display</th>
                  <th>Canonical</th>
                  <th>Type Label</th>
                  <th>Status</th>
                  <th>Resolution</th>
                  <th>Aliases</th>
                  <th>Tags</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {entities.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="emptyCell">
                      No entities loaded yet.
                    </td>
                  </tr>
                ) : (
                  entities.map((entity) => (
                    <tr key={entity.id}>
                      <td>{entity.id}</td>
                      <td>{entity.name}</td>
                      <td>{entity.display_name || "-"}</td>
                      <td>{entity.canonical_name}</td>
                      <td>{entity.type_label || entity.type}</td>
                      <td>
                        {entity.merged_into_id === null
                          ? "canonical"
                          : `merged -> #${entity.merged_into_id}`}
                      </td>
                      <td>
                        {entity.resolution_reason
                          ? `${entity.resolution_reason} (${formatScore(entity.resolution_confidence)})`
                          : `canonical (${formatScore(entity.resolution_confidence)})`}
                      </td>
                      <td>{entity.known_aliases_json.join(", ") || "-"}</td>
                      <td>{entity.tags_json.join(", ") || "-"}</td>
                      <td>{formatTimestamp(entity.updated_at)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="tableWrap">
            <table className="table mono">
              <caption>Entity Merge Audits</caption>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Survivor</th>
                  <th>Merged IDs</th>
                  <th>Reason</th>
                  <th>Confidence</th>
                  <th>Resolver</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {entityMerges.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="emptyCell">
                      No entity merges recorded for this conversation.
                    </td>
                  </tr>
                ) : (
                  entityMerges.map((merge) => (
                    <tr key={merge.id}>
                      <td>{merge.id}</td>
                      <td>#{merge.survivor_entity_id}</td>
                      <td>{merge.merged_entity_ids_json.join(", ")}</td>
                      <td>{merge.reason_for_merge}</td>
                      <td>{merge.confidence.toFixed(2)}</td>
                      <td>{merge.resolver_version}</td>
                      <td>{formatTimestamp(merge.timestamp)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="tableWrap">
            <table className="table mono">
              <caption>Resolution Events</caption>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Type</th>
                  <th>Entities</th>
                  <th>Similarity</th>
                  <th>Rationale</th>
                  <th>Source Messages</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {resolutionEvents.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="emptyCell">
                      No resolution events recorded for this conversation.
                    </td>
                  </tr>
                ) : (
                  resolutionEvents.map((event) => (
                    <tr key={event.id}>
                      <td>{event.id}</td>
                      <td>{event.event_type}</td>
                      <td>{event.entity_ids_json.join(", ") || "-"}</td>
                      <td>{formatScore(event.similarity_score)}</td>
                      <td>{event.rationale}</td>
                      <td>{event.source_message_ids_json.join(", ") || "-"}</td>
                      <td>{formatTimestamp(event.created_at)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="tableWrap">
            <table className="table mono">
              <caption>Facts</caption>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Subject</th>
                  <th>Predicate</th>
                  <th>Object</th>
                  <th>Scope</th>
                  <th>Confidence</th>
                  <th>Extractor Run</th>
                  <th>Sources</th>
                  <th>Explain</th>
                </tr>
              </thead>
              <tbody>
                {facts.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="emptyCell">
                      No facts loaded yet.
                    </td>
                  </tr>
                ) : (
                  facts.map((fact) => (
                    <tr key={fact.id}>
                      <td>{fact.id}</td>
                      <td>{fact.subject_entity_name}</td>
                      <td>{fact.predicate}</td>
                      <td>{fact.object_value}</td>
                      <td>{fact.scope}</td>
                      <td>{formatScore(fact.confidence)}</td>
                      <td>{fact.extractor_run_id ?? "-"}</td>
                      <td>{fact.source_message_ids_json.join(", ")}</td>
                      <td>
                        <button
                          className="button tableButton"
                          type="button"
                          disabled={busyLabel !== null}
                          onClick={() => {
                            void runTask(`Explain fact #${fact.id}`, async () => {
                              await loadFactExplainById(fact.id);
                            });
                          }}
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="tableWrap">
            <table className="table mono">
              <caption>Relations</caption>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>From</th>
                  <th>Relation</th>
                  <th>To</th>
                  <th>Scope</th>
                  <th>Extractor Run</th>
                  <th>Sources</th>
                  <th>Explain</th>
                </tr>
              </thead>
              <tbody>
                {relations.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="emptyCell">
                      No relations loaded yet.
                    </td>
                  </tr>
                ) : (
                  relations.map((relation) => (
                    <tr key={relation.id}>
                      <td>{relation.id}</td>
                      <td>{relation.from_entity_name}</td>
                      <td>{relation.relation_type}</td>
                      <td>{relation.to_entity_name}</td>
                      <td>{relation.scope}</td>
                      <td>{relation.extractor_run_id ?? "-"}</td>
                      <td>{relation.source_message_ids_json.join(", ")}</td>
                      <td>
                        <button
                          className="button tableButton"
                          type="button"
                          disabled={busyLabel !== null}
                          onClick={() => {
                            void runTask(`Explain relation #${relation.id}`, async () => {
                              await loadRelationExplainById(relation.id);
                            });
                          }}
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {showDatabase ? (
        <section className="panel grid">
          <div className="sectionHead">
            <h2 style={{ margin: 0 }}>Phase 2 Advanced Inspector</h2>
            <p className="muted" style={{ margin: 0 }}>
              Search, summary, graph, and timeline views from the Phase 2 knowledge endpoints.
            </p>
          </div>

          <div className="toolbar">
            <label className="field grow">
              <span className="label">Semantic Search Query</span>
              <input
                className="input"
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="Apple supply chain risk"
              />
            </label>
            <label className="toggleRow">
              <input
                type="checkbox"
                checked={searchConversationScoped}
                onChange={(event) => setSearchConversationScoped(event.target.checked)}
              />
              <span>Scope search to current conversation</span>
            </label>
            <button
              className="button"
              type="button"
              disabled={busyLabel !== null}
              onClick={() => {
                void runTask("Run semantic search", runSemanticSearch);
              }}
            >
              GET Search
            </button>
            <button
              className="button ghost"
              type="button"
              disabled={busyLabel !== null}
              onClick={() => {
                void runTask("Load conversation summary", loadConversationSummary);
              }}
            >
              GET Summary
            </button>
          </div>

          <div className="toolbar">
            <label className="field compact">
              <span className="label">Entity ID</span>
              <input
                className="input mono"
                value={entityLookupId}
                onChange={(event) => setEntityLookupId(event.target.value)}
                placeholder="1"
                inputMode="numeric"
              />
            </label>
            <button
              className="button ghost"
              type="button"
              disabled={busyLabel !== null}
              onClick={() => {
                void runTask("Load entity graph/timeline", async () => {
                  await loadEntityKnowledgeViews(parsePositiveId(entityLookupId, "Entity ID"));
                });
              }}
            >
              GET Graph + Timeline
            </button>
            <button
              className="button ghost"
              type="button"
              disabled={busyLabel !== null || canonicalEntities.length === 0}
              onClick={() => {
                const fallbackEntityId = canonicalEntities[0]?.id;
                if (!fallbackEntityId) {
                  return;
                }
                void runTask("Load canonical entity graph/timeline", async () => {
                  await loadEntityKnowledgeViews(fallbackEntityId);
                });
              }}
            >
              Load First Canonical
            </button>
          </div>

          {searchResult ? (
            <div className="grid two">
              <div className="tableWrap">
                <table className="table mono">
                  <caption>Search Entity Hits ({searchResult.entities.length})</caption>
                  <thead>
                    <tr>
                      <th>Similarity</th>
                      <th>ID</th>
                      <th>Canonical</th>
                      <th>Type</th>
                    </tr>
                  </thead>
                  <tbody>
                    {searchResult.entities.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="emptyCell">
                          No entity hits.
                        </td>
                      </tr>
                    ) : (
                      searchResult.entities.map((hit) => (
                        <tr key={`entity-hit-${hit.entity.id}`}>
                          <td>{formatScore(hit.similarity, 3)}</td>
                          <td>{hit.entity.id}</td>
                          <td>{hit.entity.canonical_name}</td>
                          <td>{hit.entity.type_label || hit.entity.type}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
              <div className="tableWrap">
                <table className="table mono">
                  <caption>Search Fact Hits ({searchResult.facts.length})</caption>
                  <thead>
                    <tr>
                      <th>Similarity</th>
                      <th>ID</th>
                      <th>Fact</th>
                      <th>Scope</th>
                    </tr>
                  </thead>
                  <tbody>
                    {searchResult.facts.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="emptyCell">
                          No fact hits.
                        </td>
                      </tr>
                    ) : (
                      searchResult.facts.map((hit) => (
                        <tr key={`fact-hit-${hit.fact.id}`}>
                          <td>{formatScore(hit.similarity, 3)}</td>
                          <td>{hit.fact.id}</td>
                          <td>
                            {hit.fact.subject_entity_name} {hit.fact.predicate} {hit.fact.object_value}
                          </td>
                          <td>{hit.fact.scope}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}

          {conversationSummary ? (
            <div className="grid">
              <div className="grid threeStats">
                <div className="miniCard">
                  <div className="miniLabel">Summary Conversation</div>
                  <div className="miniValue">{conversationSummary.conversation_id}</div>
                </div>
                <div className="miniCard">
                  <div className="miniLabel">Key Entities</div>
                  <div className="miniValue">{conversationSummary.key_entities.length}</div>
                </div>
                <div className="miniCard">
                  <div className="miniLabel">Relation Clusters</div>
                  <div className="miniValue">{conversationSummary.relation_clusters.length}</div>
                </div>
              </div>
              <div className="grid two">
                <div className="panel inset">
                  <h3 className="subhead">Schema Changes Triggered</h3>
                  <div className="mono">
                    <div>
                      nodes:{" "}
                      {conversationSummary.schema_changes_triggered.node_labels.join(", ") || "-"}
                    </div>
                    <div>
                      fields:{" "}
                      {conversationSummary.schema_changes_triggered.field_labels.join(", ") || "-"}
                    </div>
                    <div>
                      relations:{" "}
                      {conversationSummary.schema_changes_triggered.relation_labels.join(", ") || "-"}
                    </div>
                  </div>
                </div>
                <div className="panel inset">
                  <h3 className="subhead">Relation Clusters</h3>
                  {conversationSummary.relation_clusters.length === 0 ? (
                    <p className="muted" style={{ margin: 0 }}>
                      No relation clusters available.
                    </p>
                  ) : (
                    <ul className="list mono">
                      {conversationSummary.relation_clusters.map((cluster) => (
                        <li key={`cluster-${cluster.relation_label}`}>
                          {cluster.relation_label} ({cluster.relation_count}) -{" "}
                          {cluster.sample_edges.join("; ") || "no samples"}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </div>
          ) : null}

          {entityGraph ? (
            <div className="grid two">
              <div className="panel inset">
                <h3 className="subhead">
                  Entity Graph: {entityGraph.entity.canonical_name} (#{entityGraph.entity.id})
                </h3>
                <div className="mono">
                  <div>related entities: {entityGraph.related_entities.length}</div>
                  <div>outgoing: {entityGraph.outgoing_relations.length}</div>
                  <div>incoming: {entityGraph.incoming_relations.length}</div>
                  <div>supporting facts: {entityGraph.supporting_facts.length}</div>
                </div>
                {entityGraph.related_entities.length > 0 ? (
                  <ul className="list mono">
                    {entityGraph.related_entities.map((related) => (
                      <li key={`related-${related.id}`}>
                        #{related.id} {related.canonical_name}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
              <div className="panel inset">
                <h3 className="subhead">Entity Timeline</h3>
                {!entityTimeline || entityTimeline.length === 0 ? (
                  <p className="muted" style={{ margin: 0 }}>
                    No timeline facts available.
                  </p>
                ) : (
                  <ul className="list mono">
                    {entityTimeline.map((item) => (
                      <li key={`timeline-${item.fact.id}`}>
                        {item.timestamp ? formatTimestamp(item.timestamp) : "no timestamp"}:{" "}
                        {item.fact.predicate} = {item.fact.object_value}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          ) : null}
        </section>
      ) : null}

      {showExplainTools ? (
        <section className="panel grid">
          <div className="sectionHead">
            <h2 style={{ margin: 0 }}>Explainability Inspector</h2>
            <p className="muted" style={{ margin: 0 }}>
              Fetch record-level traceability for facts or relations.
            </p>
          </div>

          <div className="toolbar">
            <label className="toggleRow">
              <input
                type="checkbox"
                checked={globalExplainLookup}
                onChange={(event) => setGlobalExplainLookup(event.target.checked)}
              />
              <span>Use global explain endpoints (/facts/:id or /relations/:id)</span>
            </label>
            <label className="field compact">
              <span className="label">Fact ID</span>
              <input
                className="input mono"
                value={factExplainId}
                onChange={(event) => setFactExplainId(event.target.value)}
                placeholder="1"
                inputMode="numeric"
              />
            </label>
            <button
              className="button"
              type="button"
              disabled={busyLabel !== null}
              onClick={() => {
                void runTask("Explain fact", async () => {
                  await loadFactExplainById(parsePositiveId(factExplainId, "Fact ID"));
                });
              }}
            >
              GET Fact Explain
            </button>

            <label className="field compact">
              <span className="label">Relation ID</span>
              <input
                className="input mono"
                value={relationExplainId}
                onChange={(event) => setRelationExplainId(event.target.value)}
                placeholder="1"
                inputMode="numeric"
              />
            </label>
            <button
              className="button"
              type="button"
              disabled={busyLabel !== null}
              onClick={() => {
                void runTask("Explain relation", async () => {
                  await loadRelationExplainById(parsePositiveId(relationExplainId, "Relation ID"));
                });
              }}
            >
              GET Relation Explain
            </button>
          </div>

          {explainSelection ? (
            explainSelection.kind === "fact" ? (
              <div className="grid">
                <div className="explainHeader">
                  <span className="pill neutral mono">fact #{explainSelection.data.fact.id}</span>
                  <strong>
                    {explainSelection.data.fact.subject_entity_name}{" "}
                    {explainSelection.data.fact.predicate} {explainSelection.data.fact.object_value}
                  </strong>
                </div>
                <div className="grid threeStats">
                  <div className="miniCard">
                    <div className="miniLabel">Extractor Run</div>
                    <div className="miniValue">{explainSelection.data.extractor_run_id ?? "-"}</div>
                  </div>
                  <div className="miniCard">
                    <div className="miniLabel">Schema Status</div>
                    <div className="miniValue">{explainSelection.data.schema_canonicalization.status}</div>
                  </div>
                  <div className="miniCard">
                    <div className="miniLabel">Resolution Events</div>
                    <div className="miniValue">{explainSelection.data.resolution_events.length}</div>
                  </div>
                </div>
                <div className="grid two">
                  <div className="panel inset">
                    <h3 className="subhead">Snippets</h3>
                    {explainSelection.data.snippets.length === 0 ? (
                      <p className="muted" style={{ margin: 0 }}>
                        No exact snippets were identified.
                      </p>
                    ) : (
                      <ul className="list">
                        {explainSelection.data.snippets.map((snippet, index) => (
                          <li key={`${index}-${snippet}`}>{snippet}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                  <div className="panel inset">
                    <h3 className="subhead">Source Messages</h3>
                    <div className="stack">
                      {explainSelection.data.source_messages.map((message) => (
                        <article className="messageCard" key={message.id}>
                          <div className="messageMeta">
                            <span className="pill neutral mono">#{message.id}</span>
                            <span className="pill role">{message.role}</span>
                            <span className="mono muted">{formatTimestamp(message.timestamp)}</span>
                          </div>
                          {renderFormattedMessage(message.content)}
                        </article>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="grid two">
                  <div className="panel inset">
                    <h3 className="subhead">Schema Canonicalization</h3>
                    <div className="mono">
                      <div>table: {explainSelection.data.schema_canonicalization.registry_table}</div>
                      <div>observed: {explainSelection.data.schema_canonicalization.observed_label}</div>
                      <div>
                        canonical:{" "}
                        {explainSelection.data.schema_canonicalization.canonical_label ??
                          "(none)"}
                      </div>
                      <div>
                        canonical id:{" "}
                        {explainSelection.data.schema_canonicalization.canonical_id ?? "-"}
                      </div>
                    </div>
                  </div>
                  <div className="panel inset">
                    <h3 className="subhead">Resolution Events</h3>
                    {explainSelection.data.resolution_events.length === 0 ? (
                      <p className="muted" style={{ margin: 0 }}>
                        No related resolution events found.
                      </p>
                    ) : (
                      <ul className="list mono">
                        {explainSelection.data.resolution_events.map((event) => (
                          <li key={event.id}>
                            #{event.id} {event.event_type} entities[{event.entity_ids_json.join(", ")}]{" "}
                            sim={formatScore(event.similarity_score)} rationale={event.rationale}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="grid">
                <div className="explainHeader">
                  <span className="pill neutral mono">
                    relation #{explainSelection.data.relation.id}
                  </span>
                  <strong>
                    {explainSelection.data.relation.from_entity_name}{" "}
                    {explainSelection.data.relation.relation_type}{" "}
                    {explainSelection.data.relation.to_entity_name}
                  </strong>
                </div>
                <div className="grid threeStats">
                  <div className="miniCard">
                    <div className="miniLabel">Extractor Run</div>
                    <div className="miniValue">{explainSelection.data.extractor_run_id ?? "-"}</div>
                  </div>
                  <div className="miniCard">
                    <div className="miniLabel">Schema Status</div>
                    <div className="miniValue">{explainSelection.data.schema_canonicalization.status}</div>
                  </div>
                  <div className="miniCard">
                    <div className="miniLabel">Resolution Events</div>
                    <div className="miniValue">{explainSelection.data.resolution_events.length}</div>
                  </div>
                </div>
                <div className="grid two">
                  <div className="panel inset">
                    <h3 className="subhead">Snippets</h3>
                    {explainSelection.data.snippets.length === 0 ? (
                      <p className="muted" style={{ margin: 0 }}>
                        No exact snippets were identified.
                      </p>
                    ) : (
                      <ul className="list">
                        {explainSelection.data.snippets.map((snippet, index) => (
                          <li key={`${index}-${snippet}`}>{snippet}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                  <div className="panel inset">
                    <h3 className="subhead">Source Messages</h3>
                    <div className="stack">
                      {explainSelection.data.source_messages.map((message) => (
                        <article className="messageCard" key={message.id}>
                          <div className="messageMeta">
                            <span className="pill neutral mono">#{message.id}</span>
                            <span className="pill role">{message.role}</span>
                            <span className="mono muted">{formatTimestamp(message.timestamp)}</span>
                          </div>
                          {renderFormattedMessage(message.content)}
                        </article>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="grid two">
                  <div className="panel inset">
                    <h3 className="subhead">Schema Canonicalization</h3>
                    <div className="mono">
                      <div>table: {explainSelection.data.schema_canonicalization.registry_table}</div>
                      <div>observed: {explainSelection.data.schema_canonicalization.observed_label}</div>
                      <div>
                        canonical:{" "}
                        {explainSelection.data.schema_canonicalization.canonical_label ??
                          "(none)"}
                      </div>
                      <div>
                        canonical id:{" "}
                        {explainSelection.data.schema_canonicalization.canonical_id ?? "-"}
                      </div>
                    </div>
                  </div>
                  <div className="panel inset">
                    <h3 className="subhead">Resolution Events</h3>
                    {explainSelection.data.resolution_events.length === 0 ? (
                      <p className="muted" style={{ margin: 0 }}>
                        No related resolution events found.
                      </p>
                    ) : (
                      <ul className="list mono">
                        {explainSelection.data.resolution_events.map((event) => (
                          <li key={event.id}>
                            #{event.id} {event.event_type} entities[{event.entity_ids_json.join(", ")}]{" "}
                            sim={formatScore(event.similarity_score)} rationale={event.rationale}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              </div>
            )
          ) : (
            <p className="muted" style={{ margin: 0 }}>
              No explainability result loaded yet.
            </p>
          )}
        </section>
      ) : null}
    </main>
  );
}
