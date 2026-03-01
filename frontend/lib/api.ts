export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

let appWarmupPromise: Promise<void> | null = null;
const GET_CACHE_TTL_MS = 30_000;
type GetCacheEntry = { expiresAt: number; payload: unknown };
const getResponseCache = new Map<string, GetCacheEntry>();
const inFlightGetRequests = new Map<string, Promise<unknown>>();

type ApiResponse<T> = {
  data: T;
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

function buildQuery(params: Record<string, string | number | boolean | null | undefined>): string {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === null || value === undefined || value === "") {
      return;
    }
    query.set(key, String(value));
  });
  const encoded = query.toString();
  return encoded ? `?${encoded}` : "";
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method ?? "GET").toUpperCase();
  const url = `${API_BASE_URL}${path}`;
  const headers = {
    "Content-Type": "application/json",
    ...(init?.headers ?? {})
  };

  if (method === "GET") {
    const cached = getResponseCache.get(url);
    if (cached && cached.expiresAt > Date.now()) {
      return cached.payload as T;
    }

    const inFlight = inFlightGetRequests.get(url);
    if (inFlight) {
      return (await inFlight) as T;
    }

    const requestPromise = (async () => {
      const response = await fetch(url, {
        ...init,
        method,
        headers,
        cache: "no-store"
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

      const payload = (await response.json()) as T;
      getResponseCache.set(url, {
        payload,
        expiresAt: Date.now() + GET_CACHE_TTL_MS
      });
      return payload;
    })().finally(() => {
      inFlightGetRequests.delete(url);
    });

    inFlightGetRequests.set(url, requestPromise);
    return (await requestPromise) as T;
  }

  const response = await fetch(url, {
    ...init,
    method,
    headers
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

async function apiGet<T>(path: string): Promise<T> {
  const response = await requestJson<ApiResponse<T>>(path, { method: "GET" });
  return response.data;
}

async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const response = await requestJson<ApiResponse<T>>(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body)
  });
  getResponseCache.clear();
  return response.data;
}

async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const response = await requestJson<ApiResponse<T>>(path, {
    method: "PATCH",
    body: JSON.stringify(body)
  });
  getResponseCache.clear();
  return response.data;
}

async function apiDelete<T>(path: string): Promise<T> {
  const response = await requestJson<ApiResponse<T>>(path, { method: "DELETE" });
  getResponseCache.clear();
  return response.data;
}

export type MessageRead = {
  id: number;
  conversation_id: string;
  role: string;
  content: string;
  timestamp: string;
};

export type EntityRead = {
  id: number;
  conversation_id: string;
  name: string;
  display_name: string;
  canonical_name: string;
  type: string;
  type_label: string;
  aliases_json: string[];
  known_aliases_json: string[];
  tags_json: string[];
  first_seen_timestamp: string;
  resolution_confidence: number;
  resolution_reason: string | null;
  resolver_version: string | null;
  merged_into_id: number | null;
  created_at: string;
  updated_at: string;
};

export type FactWithSubjectRead = {
  id: number;
  conversation_id: string;
  subject_entity_id: number;
  subject_entity_name: string;
  predicate: string;
  object_value: string;
  scope: string;
  confidence: number;
  source_message_ids_json: number[];
  extractor_run_id: number | null;
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
  scope: string;
  confidence: number;
  qualifiers_json: Record<string, unknown>;
  source_message_ids_json: number[];
  extractor_run_id: number | null;
  created_at: string;
};

export type ConversationSchemaChanges = {
  node_labels: string[];
  field_labels: string[];
  relation_labels: string[];
};

export type RelationCluster = {
  relation_label: string;
  relation_count: number;
  sample_edges: string[];
};

export type ConversationSummaryData = {
  conversation_id: string;
  key_entities: EntityRead[];
  key_facts: FactWithSubjectRead[];
  schema_changes_triggered: ConversationSchemaChanges;
  relation_clusters: RelationCluster[];
};

export type ConversationGraphData = {
  conversation_id: string;
  entities: EntityRead[];
  relations: RelationWithEntitiesRead[];
};

export type EntityGraphData = {
  entity: EntityRead;
  outgoing_relations: RelationWithEntitiesRead[];
  incoming_relations: RelationWithEntitiesRead[];
  related_entities: EntityRead[];
  supporting_facts: FactWithSubjectRead[];
};

export type FactTimelineItem = {
  fact: FactWithSubjectRead;
  timestamp: string | null;
};

export type SemanticSearchData = {
  query: string;
  conversation_id: string | null;
  type_label: string | null;
  start_time: string | null;
  end_time: string | null;
  entities: Array<{ entity: EntityRead; similarity: number }>;
  facts: Array<{ fact: FactWithSubjectRead; similarity: number }>;
};

export type ResolutionEventRead = {
  id: number;
  conversation_id: string;
  event_type: string;
  entity_ids_json: number[];
  similarity_score: number | null;
  rationale: string;
  source_message_ids_json: number[];
  created_at: string;
};

export type SourceMessageEvidence = {
  id: number;
  role: string;
  content: string;
  timestamp: string;
};

export type SchemaCanonicalizationInfo = {
  registry_table: string;
  observed_label: string;
  canonical_label: string | null;
  canonical_id: number | null;
  status: string;
  proposal: SchemaProposalLink | null;
};

export type SchemaProposalLink = {
  proposal_id: number;
  proposal_type: string;
  status: string;
  confidence: number;
  created_at: string;
};

export type ExtractionMetadata = {
  extractor_run_id: number;
  model_name: string;
  prompt_version: string;
  created_at: string;
};

export type FactExplainData = {
  fact: FactWithSubjectRead;
  extractor_run_id: number | null;
  extraction_metadata: ExtractionMetadata | null;
  source_messages: SourceMessageEvidence[];
  resolution_events: ResolutionEventRead[];
  schema_canonicalization: SchemaCanonicalizationInfo;
  snippets: string[];
};

export type RelationExplainData = {
  relation: RelationWithEntitiesRead;
  extractor_run_id: number | null;
  extraction_metadata: ExtractionMetadata | null;
  source_messages: SourceMessageEvidence[];
  resolution_events: ResolutionEventRead[];
  schema_canonicalization: SchemaCanonicalizationInfo;
  snippets: string[];
};

export type ConversationListItem = {
  conversation_id: string;
  first_message_at: string | null;
  last_message_at: string | null;
  message_count: number;
  entity_count: number;
  fact_count: number;
  relation_count: number;
  extractor_run_count: number;
};

export type ConversationsListResponse = {
  items: ConversationListItem[];
  total: number;
  limit: number;
  offset: number;
};

export type RecentEntityItem = {
  entity_id: number;
  canonical_name: string;
  display_name: string;
  type_label: string;
  alias_count: number;
  first_seen: string;
  last_seen: string;
  conversation_count: number;
};

export type RecentEntitiesResponse = {
  items: RecentEntityItem[];
};

export type EntityListItem = {
  id: number;
  canonical_name: string;
  display_name: string;
  type_label: string;
  alias_count: number;
  first_seen: string;
  last_seen: string;
  conversation_count: number;
  dynamic_fields: Record<string, string>;
};

export type EntityListingResponse = {
  items: EntityListItem[];
  total: number;
  limit: number;
  offset: number;
  selected_fields: string[];
  available_fields: string[];
};

export type SchemaNodeOverview = {
  id: number;
  label: string;
  description: string | null;
  examples: string[];
  frequency: number;
  last_seen_conversation_id: string | null;
};

export type SchemaFieldOverview = {
  id: number;
  label: string;
  canonical_label: string | null;
  description: string | null;
  examples: string[];
  frequency: number;
  last_seen_conversation_id: string | null;
};

export type SchemaRelationOverview = {
  id: number;
  label: string;
  canonical_label: string | null;
  description: string | null;
  examples: string[];
  frequency: number;
  last_seen_conversation_id: string | null;
};

export type SchemaProposalOverview = {
  id: number;
  proposal_type: string;
  status: string;
  confidence: number;
  payload: Record<string, unknown>;
  evidence: Record<string, unknown>;
  created_at: string;
};

export type SchemaOverviewData = {
  nodes: SchemaNodeOverview[];
  fields: SchemaFieldOverview[];
  relations: SchemaRelationOverview[];
  proposals: SchemaProposalOverview[];
};

export type ExtractionRunResult = {
  extractor_run_id: number | null;
  conversation_id: string;
  messages_processed: number;
  entities_created: number;
  facts_created: number;
  relations_created: number;
};

export type LiveChatTurnResult = {
  conversation_id: string;
  user_message: MessageRead;
  assistant_message: MessageRead;
  extraction: ExtractionRunResult | null;
};

export type DeleteResult = {
  id: number;
  deleted: boolean;
};

export type ConversationDeleteResult = {
  conversation_id: string;
  deleted: boolean;
};

export type SchemaNodeMutationRead = {
  id: number;
  label: string;
  description: string | null;
  examples_json: string[];
};

export type SchemaFieldMutationRead = {
  id: number;
  label: string;
  canonical_of_id: number | null;
  description: string | null;
  examples_json: string[];
};

export type SchemaRelationMutationRead = {
  id: number;
  label: string;
  canonical_of_id: number | null;
  description: string | null;
  examples_json: string[];
};

export async function getConversations(params?: {
  limit?: number;
  offset?: number;
  q?: string;
}): Promise<ConversationsListResponse> {
  const query = buildQuery({
    limit: params?.limit ?? 20,
    offset: params?.offset ?? 0,
    q: params?.q ?? null
  });
  return apiGet<ConversationsListResponse>(`/conversations${query}`);
}

export async function getRecentEntities(limit = 12): Promise<RecentEntitiesResponse> {
  const query = buildQuery({ limit });
  return apiGet<RecentEntitiesResponse>(`/recent/entities${query}`);
}

export async function getEntitiesCatalog(params?: {
  limit?: number;
  offset?: number;
  sort?: "canonical_name" | "type_label" | "last_seen" | "conversation_count" | "alias_count";
  order?: "asc" | "desc";
  q?: string;
  type_label?: string;
  fields?: string[];
}): Promise<EntityListingResponse> {
  const query = buildQuery({
    limit: params?.limit ?? 25,
    offset: params?.offset ?? 0,
    sort: params?.sort ?? "last_seen",
    order: params?.order ?? "desc",
    q: params?.q ?? null,
    type_label: params?.type_label ?? null,
    fields: params?.fields && params.fields.length > 0 ? params.fields.join(",") : null
  });
  return apiGet<EntityListingResponse>(`/entities${query}`);
}

export async function getConversationMessages(conversationId: string): Promise<MessageRead[]> {
  return apiGet<MessageRead[]>(`/conversations/${encodeURIComponent(conversationId)}/messages`);
}

export async function getConversationSummary(conversationId: string): Promise<ConversationSummaryData> {
  return apiGet<ConversationSummaryData>(
    `/conversations/${encodeURIComponent(conversationId)}/summary`
  );
}

export async function getConversationGraph(conversationId: string): Promise<ConversationGraphData> {
  return apiGet<ConversationGraphData>(
    `/conversations/${encodeURIComponent(conversationId)}/graph`
  );
}

export async function rerunExtraction(conversationId: string): Promise<ExtractionRunResult> {
  return apiPost<ExtractionRunResult>(`/conversations/${encodeURIComponent(conversationId)}/extract`);
}

export async function runLiveChatTurn(
  conversationId: string,
  payload: { content: string; auto_extract?: boolean; system_prompt?: string }
): Promise<LiveChatTurnResult> {
  return apiPost<LiveChatTurnResult>(
    `/conversations/${encodeURIComponent(conversationId)}/chat/turn`,
    payload
  );
}

export async function getEntity(entityId: number): Promise<EntityRead> {
  return apiGet<EntityRead>(`/entities/${entityId}`);
}

export async function getEntityGraph(entityId: number): Promise<EntityGraphData> {
  return apiGet<EntityGraphData>(`/entities/${entityId}/graph`);
}

export async function getEntityTimeline(entityId: number): Promise<FactTimelineItem[]> {
  return apiGet<FactTimelineItem[]>(`/entities/${entityId}/timeline`);
}

export async function runSemanticSearch(params: {
  q: string;
  conversation_id?: string;
  type_label?: string;
  start_time?: string;
  end_time?: string;
  limit?: number;
}): Promise<SemanticSearchData> {
  const query = buildQuery({
    q: params.q,
    conversation_id: params.conversation_id ?? null,
    type_label: params.type_label ?? null,
    start_time: params.start_time ?? null,
    end_time: params.end_time ?? null,
    limit: params.limit ?? 12
  });
  return apiGet<SemanticSearchData>(`/search${query}`);
}

export async function getSchemaOverview(params?: {
  limit?: number;
  proposal_limit?: number;
}): Promise<SchemaOverviewData> {
  const query = buildQuery({
    limit: params?.limit ?? 200,
    proposal_limit: params?.proposal_limit ?? 100
  });
  return apiGet<SchemaOverviewData>(`/schema/overview${query}`);
}

export async function getFactExplain(factId: number): Promise<FactExplainData> {
  return apiGet<FactExplainData>(`/facts/${factId}/explain`);
}

export async function getRelationExplain(relationId: number): Promise<RelationExplainData> {
  return apiGet<RelationExplainData>(`/relations/${relationId}/explain`);
}

export async function updateMessage(
  messageId: number,
  payload: { role?: "user" | "assistant"; content?: string }
): Promise<MessageRead> {
  return apiPatch<MessageRead>(`/messages/${messageId}`, payload);
}

export async function deleteMessage(messageId: number): Promise<DeleteResult> {
  return apiDelete<DeleteResult>(`/messages/${messageId}`);
}

export async function deleteConversation(conversationId: string): Promise<ConversationDeleteResult> {
  return apiDelete<ConversationDeleteResult>(`/conversations/${encodeURIComponent(conversationId)}`);
}

export async function updateEntityRecord(
  entityId: number,
  payload: {
    canonical_name?: string;
    display_name?: string;
    type_label?: string;
    type?: string;
    known_aliases_json?: string[];
    aliases_json?: string[];
    tags_json?: string[];
  }
): Promise<EntityRead> {
  return apiPatch<EntityRead>(`/entities/${entityId}`, payload);
}

export async function deleteEntityRecord(entityId: number): Promise<DeleteResult> {
  return apiDelete<DeleteResult>(`/entities/${entityId}`);
}

export async function updateFact(
  factId: number,
  payload: {
    subject_entity_id?: number;
    predicate?: string;
    object_value?: string;
    scope?: string;
    confidence?: number;
  }
): Promise<FactWithSubjectRead> {
  return apiPatch<FactWithSubjectRead>(`/facts/${factId}`, payload);
}

export async function deleteFact(factId: number): Promise<DeleteResult> {
  return apiDelete<DeleteResult>(`/facts/${factId}`);
}

export async function updateRelation(
  relationId: number,
  payload: {
    from_entity_id?: number;
    to_entity_id?: number;
    relation_type?: string;
    scope?: string;
    confidence?: number;
    qualifiers_json?: Record<string, unknown>;
  }
): Promise<RelationWithEntitiesRead> {
  return apiPatch<RelationWithEntitiesRead>(`/relations/${relationId}`, payload);
}

export async function deleteRelation(relationId: number): Promise<DeleteResult> {
  return apiDelete<DeleteResult>(`/relations/${relationId}`);
}

export async function updateSchemaNode(
  schemaNodeId: number,
  payload: { label?: string; description?: string | null; examples_json?: string[] }
): Promise<SchemaNodeMutationRead> {
  return apiPatch<SchemaNodeMutationRead>(`/schema/nodes/${schemaNodeId}`, payload);
}

export async function deleteSchemaNode(schemaNodeId: number): Promise<DeleteResult> {
  return apiDelete<DeleteResult>(`/schema/nodes/${schemaNodeId}`);
}

export async function updateSchemaField(
  schemaFieldId: number,
  payload: {
    label?: string;
    description?: string | null;
    examples_json?: string[];
    canonical_of_id?: number;
  }
): Promise<SchemaFieldMutationRead> {
  return apiPatch<SchemaFieldMutationRead>(`/schema/fields/${schemaFieldId}`, payload);
}

export async function deleteSchemaField(schemaFieldId: number): Promise<DeleteResult> {
  return apiDelete<DeleteResult>(`/schema/fields/${schemaFieldId}`);
}

export async function updateSchemaRelation(
  schemaRelationId: number,
  payload: {
    label?: string;
    description?: string | null;
    examples_json?: string[];
    canonical_of_id?: number;
  }
): Promise<SchemaRelationMutationRead> {
  return apiPatch<SchemaRelationMutationRead>(`/schema/relations/${schemaRelationId}`, payload);
}

export async function deleteSchemaRelation(schemaRelationId: number): Promise<DeleteResult> {
  return apiDelete<DeleteResult>(`/schema/relations/${schemaRelationId}`);
}

export function warmWorkspaceApi(): Promise<void> {
  if (appWarmupPromise) {
    return appWarmupPromise;
  }

  appWarmupPromise = Promise.allSettled([
    getConversations({ limit: 20, offset: 0 }),
    getConversations({ limit: 200, offset: 0 }),
    getRecentEntities(12),
    getEntitiesCatalog({ limit: 25, offset: 0, sort: "last_seen", order: "desc" }),
    getSchemaOverview({ limit: 200, proposal_limit: 200 })
  ]).then(() => undefined);

  return appWarmupPromise;
}
