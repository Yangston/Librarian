export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export type ApiResponse<T> = {
  data: T;
};

export type MessageRole = "user" | "assistant";

export type MessageCreateInput = {
  role: MessageRole;
  content: string;
  timestamp?: string | null;
};

export type MessagesIngestRequest = {
  messages: MessageCreateInput[];
};

export type MessageRead = {
  id: number;
  conversation_id: string;
  role: string;
  content: string;
  timestamp: string;
};

export type ExtractionRunResult = {
  conversation_id: string;
  messages_processed: number;
  entities_created: number;
  facts_created: number;
  relations_created: number;
};

export type LiveChatTurnRequest = {
  content: string;
  auto_extract?: boolean;
  system_prompt?: string | null;
};

export type LiveChatTurnResult = {
  conversation_id: string;
  user_message: MessageRead;
  assistant_message: MessageRead;
  extraction: ExtractionRunResult | null;
};

export type EntityRead = {
  id: number;
  conversation_id: string;
  name: string;
  canonical_name: string;
  type: string;
  aliases_json: string[];
  known_aliases_json: string[];
  tags_json: string[];
  first_seen_timestamp: string;
  resolution_confidence: number;
  resolution_reason: string | null;
  resolver_version: string | null;
  merged_into_id: number | null;
  created_at: string;
};

export type EntityMergeAuditRead = {
  id: number;
  conversation_id: string;
  survivor_entity_id: number;
  merged_entity_ids_json: number[];
  reason_for_merge: string;
  confidence: number;
  resolver_version: string;
  details_json: Record<string, unknown>;
  timestamp: string;
};

export type PredicateRegistryEntryRead = {
  id: number;
  kind: "fact_predicate" | "relation_type" | string;
  predicate: string;
  aliases_json: string[];
  frequency: number;
  first_seen_at: string;
  last_seen_at: string;
};

export type FactWithSubjectRead = {
  id: number;
  conversation_id: string;
  subject_entity_id: number;
  subject_entity_name: string;
  predicate: string;
  object_value: string;
  confidence: number;
  source_message_ids_json: number[];
  created_at: string;
};

export type RelationWithEntitiesRead = {
  id: number;
  conversation_id: string;
  from_entity_id: number;
  from_entity_name: string;
  relation_type: string;
  to_entity_id: number;
  to_entity_name: string;
  qualifiers_json: Record<string, unknown>;
  source_message_ids_json: number[];
  created_at: string;
};

export type SourceMessageEvidence = {
  id: number;
  role: string;
  content: string;
  timestamp: string;
};

export type FactExplainData = {
  fact: FactWithSubjectRead;
  source_messages: SourceMessageEvidence[];
  snippets: string[];
};

export type RelationExplainData = {
  relation: RelationWithEntitiesRead;
  source_messages: SourceMessageEvidence[];
  snippets: string[];
};

type ApiErrorPayload = {
  detail?: unknown;
};

function formatApiError(status: number, payload: ApiErrorPayload | null): string {
  const detail = payload?.detail;
  if (typeof detail === "string") {
    return `Request failed (${status}): ${detail}`;
  }
  if (Array.isArray(detail)) {
    return `Request failed (${status}): ${detail
      .map((item) => (typeof item === "string" ? item : JSON.stringify(item)))
      .join("; ")}`;
  }
  return `Request failed (${status})`;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    cache: init?.method && init.method !== "GET" ? undefined : "no-store"
  });

  if (!response.ok) {
    let payload: ApiErrorPayload | null = null;
    try {
      payload = (await response.json()) as ApiErrorPayload;
    } catch {
      payload = null;
    }
    throw new Error(formatApiError(response.status, payload));
  }

  return (await response.json()) as T;
}

export async function fetchJson<T>(path: string): Promise<T> {
  return requestJson<T>(path, { method: "GET" });
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await requestJson<ApiResponse<T>>(path, { method: "GET" });
  return response.data;
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const response = await requestJson<ApiResponse<T>>(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body)
  });
  return response.data;
}
