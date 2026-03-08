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
      let response: Response;
      try {
        response = await fetch(url, {
          ...init,
          method,
          headers,
          cache: "no-store"
        });
      } catch (error) {
        throw new Error(
          `Network request failed for ${url}. Verify backend is running and CORS/API base URL are correct.`
        );
      }

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
  }).catch(() => {
    throw new Error(
      `Network request failed for ${url}. Verify backend is running and CORS/API base URL are correct.`
    );
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
  pod_id: number | null;
  collection_id: number | null;
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
  pod_id: number | null;
  pod_name: string | null;
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

export type PodRead = {
  id: number;
  slug: string;
  name: string;
  description: string | null;
  is_default: boolean;
  created_at: string;
  updated_at: string;
};

export type CollectionRead = {
  id: number;
  pod_id: number;
  parent_id: number | null;
  kind: string;
  slug: string;
  name: string;
  description: string | null;
  schema_json: Record<string, unknown>;
  view_config_json: Record<string, unknown>;
  sort_order: number;
  is_auto_generated: boolean;
  created_at: string;
  updated_at: string;
};

export type CollectionTreeNode = {
  collection: CollectionRead;
  children: CollectionTreeNode[];
};

export type PodTreeData = {
  pod: PodRead;
  tree: CollectionTreeNode[];
};

export type CollectionItemsResponse = {
  collection: CollectionRead;
  items: EntityListItem[];
  total: number;
  limit: number;
  offset: number;
  selected_fields: string[];
  available_fields: string[];
};

export type CollectionItemMutationResponse = {
  collection_id: number;
  entity_id: number;
  added: boolean;
};

export type ScopedGraphNode = {
  entity_id: number;
  canonical_name: string;
  display_name: string;
  type_label: string;
  external: boolean;
  pending_suggestion_count: number;
};

export type ScopedGraphEdge = {
  relation_id: number;
  from_entity_id: number;
  to_entity_id: number;
  relation_type: string;
  confidence: number;
  source_kind: string;
  status: string;
  suggested: boolean;
};

export type ScopedGraphData = {
  scope_mode: "global" | "pod" | "collection";
  pod_id: number | null;
  collection_id: number | null;
  one_hop: boolean;
  include_external: boolean;
  nodes: ScopedGraphNode[];
  edges: ScopedGraphEdge[];
  pending_suggestion_count: number;
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
  workspace_enrichment_run_id: number | null;
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

export type SpaceV2 = {
  id: number;
  slug: string;
  name: string;
  description: string | null;
  page_count: number;
  item_count: number;
  created_at: string;
  updated_at: string;
  technical_details?: Record<string, unknown> | null;
};

export type SpacePageV2 = {
  id: number;
  space_id: number;
  parent_id: number | null;
  kind: "page" | "table";
  slug: string;
  name: string;
  description: string | null;
  sort_order: number;
  item_count: number;
  updated_at: string;
  technical_details?: Record<string, unknown> | null;
};

export type SpacePagesResponseV2 = {
  space_id: number;
  items: SpacePageV2[];
};

export type LibraryItemPropertyV2 = {
  property_key: string;
  label: string;
  value: string;
  claim_index_id: number | null;
  claim_kind?: string | null;
  claim_id?: number | null;
  last_observed_at?: string | null;
};

export type LibraryItemRowV2 = {
  id: number;
  entity_id: number;
  name: string;
  type_label: string;
  summary: string | null;
  mention_count: number;
  last_seen_at: string;
  space_id: number | null;
  space_name: string | null;
  page_id: number | null;
  page_name: string | null;
  key_properties: LibraryItemPropertyV2[];
  technical_details?: Record<string, unknown> | null;
};

export type LibraryItemsResponseV2 = {
  items: LibraryItemRowV2[];
  total: number;
  limit: number;
  offset: number;
};

export type LibraryItemLinkV2 = {
  relation_type: string;
  relation_count: number;
  direction: "incoming" | "outgoing";
  other_item_id: number;
  other_item_name: string;
  last_seen_at: string;
};

export type LibraryItemActivityRowV2 = {
  claim_index_id: number;
  claim_kind: "fact" | "relation";
  claim_id: number;
  label: string;
  value_text: string | null;
  confidence: number | null;
  occurred_at: string;
  related_item_id: number | null;
  related_item_name: string | null;
  technical_details?: Record<string, unknown> | null;
};

export type LibraryItemActivityResponseV2 = {
  item_id: number;
  items: LibraryItemActivityRowV2[];
};

export type LibraryItemDetailV2 = {
  id: number;
  entity_id: number;
  name: string;
  type_label: string;
  summary: string | null;
  mention_count: number;
  last_seen_at: string;
  space_id: number | null;
  space_name: string | null;
  page_id: number | null;
  page_name: string | null;
  properties: LibraryItemPropertyV2[];
  links: LibraryItemLinkV2[];
  activity_preview: LibraryItemActivityRowV2[];
  technical_details?: Record<string, unknown> | null;
};

export type PropertyCatalogRowV2 = {
  id: number;
  display_label: string;
  kind: "field" | "relation";
  status: "stable" | "emerging" | "deprecated";
  mention_count: number;
  last_seen_at: string | null;
  technical_details?: Record<string, unknown> | null;
};

export type PropertyCatalogResponseV2 = {
  items: PropertyCatalogRowV2[];
  total: number;
};

export type UnifiedClaimExplainV2 = {
  claim_index_id: number;
  claim_kind: "fact" | "relation";
  claim_id: number;
  title: string;
  why_this_exists: string;
  evidence_snippets: string[];
  source_messages: SourceMessageEvidence[];
  canonicalization: SchemaCanonicalizationInfo | null;
  technical_details?: Record<string, unknown> | null;
};

export type SearchResultCardV2 = {
  id: string;
  kind: "item" | "claim";
  title: string;
  subtitle: string | null;
  score: number;
  href: string;
  technical_details?: Record<string, unknown> | null;
};

export type SearchResultGroupV2 = {
  key: "items" | "claims";
  label: string;
  count: number;
  items: SearchResultCardV2[];
};

export type SearchV2Response = {
  query: string;
  groups: SearchResultGroupV2[];
};

export async function getConversations(params?: {
  limit?: number;
  offset?: number;
  q?: string;
  pod_id?: number;
}): Promise<ConversationsListResponse> {
  const query = buildQuery({
    limit: params?.limit ?? 20,
    offset: params?.offset ?? 0,
    q: params?.q ?? null,
    pod_id: params?.pod_id ?? null
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
  pod_id?: number;
  collection_id?: number;
}): Promise<EntityListingResponse> {
  const query = buildQuery({
    limit: params?.limit ?? 25,
    offset: params?.offset ?? 0,
    sort: params?.sort ?? "last_seen",
    order: params?.order ?? "desc",
    q: params?.q ?? null,
    type_label: params?.type_label ?? null,
    fields: params?.fields && params.fields.length > 0 ? params.fields.join(",") : null,
    pod_id: params?.pod_id ?? null,
    collection_id: params?.collection_id ?? null
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
  payload: {
    content: string;
    pod_id?: number;
    auto_extract?: boolean;
    system_prompt?: string;
    workspace_enrichment_include_sources?: boolean;
  }
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
  pod_id?: number;
  collection_id?: number;
  start_time?: string;
  end_time?: string;
  limit?: number;
}): Promise<SemanticSearchData> {
  const query = buildQuery({
    q: params.q,
    conversation_id: params.conversation_id ?? null,
    type_label: params.type_label ?? null,
    pod_id: params.pod_id ?? null,
    collection_id: params.collection_id ?? null,
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

export async function getPods(): Promise<PodRead[]> {
  return apiGet<PodRead[]>("/pods");
}

export async function createPod(payload: {
  name: string;
  description?: string | null;
}): Promise<PodRead> {
  return apiPost<PodRead>("/pods", payload);
}

export async function deletePod(podId: number): Promise<{
  pod_id: number;
  deleted: boolean;
  conversations_deleted: number;
}> {
  return apiDelete<{
    pod_id: number;
    deleted: boolean;
    conversations_deleted: number;
  }>(`/pods/${podId}`);
}

export async function getPod(podId: number): Promise<PodRead> {
  return apiGet<PodRead>(`/pods/${podId}`);
}

export async function getPodTree(podId: number): Promise<PodTreeData> {
  return apiGet<PodTreeData>(`/pods/${podId}/tree`);
}

export async function getCollection(collectionId: number): Promise<CollectionRead> {
  return apiGet<CollectionRead>(`/collections/${collectionId}`);
}

export async function getCollectionItems(params: {
  collection_id: number;
  limit?: number;
  offset?: number;
  sort?: "canonical_name" | "type_label" | "last_seen" | "conversation_count" | "alias_count";
  order?: "asc" | "desc";
  q?: string;
  fields?: string[];
}): Promise<CollectionItemsResponse> {
  const query = buildQuery({
    limit: params.limit ?? 25,
    offset: params.offset ?? 0,
    sort: params.sort ?? "last_seen",
    order: params.order ?? "desc",
    q: params.q ?? null,
    fields: params.fields && params.fields.length > 0 ? params.fields.join(",") : null
  });
  return apiGet<CollectionItemsResponse>(`/collections/${params.collection_id}/items${query}`);
}

export async function addCollectionItem(
  collectionId: number,
  payload: { entity_id: number; sort_key?: string | null }
): Promise<CollectionItemMutationResponse> {
  return apiPost<CollectionItemMutationResponse>(`/collections/${collectionId}/items`, payload);
}

export async function removeCollectionItem(
  collectionId: number,
  entityId: number
): Promise<CollectionItemMutationResponse> {
  return apiDelete<CollectionItemMutationResponse>(`/collections/${collectionId}/items/${entityId}`);
}

export async function getScopedGraph(params?: {
  scope_mode?: "global" | "pod" | "collection";
  pod_id?: number;
  collection_id?: number;
  one_hop?: boolean;
  include_external?: boolean;
}): Promise<ScopedGraphData> {
  const query = buildQuery({
    scope_mode: params?.scope_mode ?? "global",
    pod_id: params?.pod_id ?? null,
    collection_id: params?.collection_id ?? null,
    one_hop: params?.one_hop ?? false,
    include_external: params?.include_external ?? false
  });
  return apiGet<ScopedGraphData>(`/graph/scoped${query}`);
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

export async function getSpacesV2(params?: {
  include_technical?: boolean;
}): Promise<SpaceV2[]> {
  const query = buildQuery({
    include_technical: params?.include_technical ?? false
  });
  return apiGet<SpaceV2[]>(`/v2/spaces${query}`);
}

export async function createSpaceV2(payload: {
  name: string;
  description?: string | null;
  include_technical?: boolean;
}): Promise<SpaceV2> {
  const query = buildQuery({
    include_technical: payload.include_technical ?? false
  });
  return apiPost<SpaceV2>(`/v2/spaces${query}`, {
    name: payload.name,
    description: payload.description
  });
}

export async function updateSpaceV2(
  spaceId: number,
  payload: {
    name?: string;
    description?: string | null;
    include_technical?: boolean;
  }
): Promise<SpaceV2> {
  const query = buildQuery({
    include_technical: payload.include_technical ?? false
  });
  return apiPatch<SpaceV2>(`/v2/spaces/${spaceId}${query}`, {
    name: payload.name,
    description: payload.description
  });
}

export async function deleteSpaceV2(spaceId: number): Promise<{ space_id: number; deleted: boolean }> {
  return apiDelete<{ space_id: number; deleted: boolean }>(`/v2/spaces/${spaceId}`);
}

export async function getSpacePagesV2(
  spaceId: number,
  params?: { include_technical?: boolean }
): Promise<SpacePagesResponseV2> {
  const query = buildQuery({
    include_technical: params?.include_technical ?? false
  });
  return apiGet<SpacePagesResponseV2>(`/v2/spaces/${spaceId}/pages${query}`);
}

export async function getLibraryItemsV2(params?: {
  limit?: number;
  offset?: number;
  q?: string;
  type_label?: string;
  space_id?: number;
  page_id?: number;
  sort?: "last_active" | "name" | "mentions" | "type";
  order?: "asc" | "desc";
  include_technical?: boolean;
}): Promise<LibraryItemsResponseV2> {
  const query = buildQuery({
    limit: params?.limit ?? 25,
    offset: params?.offset ?? 0,
    q: params?.q ?? null,
    type_label: params?.type_label ?? null,
    space_id: params?.space_id ?? null,
    page_id: params?.page_id ?? null,
    sort: params?.sort ?? "last_active",
    order: params?.order ?? "desc",
    include_technical: params?.include_technical ?? false
  });
  return apiGet<LibraryItemsResponseV2>(`/v2/library/items${query}`);
}

export async function getLibraryItemV2(
  itemId: number,
  params?: { include_technical?: boolean }
): Promise<LibraryItemDetailV2> {
  const query = buildQuery({ include_technical: params?.include_technical ?? false });
  return apiGet<LibraryItemDetailV2>(`/v2/library/items/${itemId}${query}`);
}

export async function updateLibraryItemV2(
  itemId: number,
  payload: {
    canonical_name?: string;
    display_name?: string;
    type_label?: string;
    type?: string;
    known_aliases_json?: string[];
    aliases_json?: string[];
    tags_json?: string[];
    include_technical?: boolean;
  }
): Promise<LibraryItemDetailV2> {
  const query = buildQuery({ include_technical: payload.include_technical ?? false });
  return apiPatch<LibraryItemDetailV2>(`/v2/library/items/${itemId}${query}`, payload);
}

export async function getLibraryItemActivityV2(
  itemId: number,
  params?: { limit?: number; include_technical?: boolean }
): Promise<LibraryItemActivityResponseV2> {
  const query = buildQuery({
    limit: params?.limit ?? 50,
    include_technical: params?.include_technical ?? false
  });
  return apiGet<LibraryItemActivityResponseV2>(`/v2/library/items/${itemId}/activity${query}`);
}

export async function getPropertiesCatalogV2(params?: {
  q?: string;
  status?: "stable" | "emerging" | "deprecated";
  kind?: "field" | "relation";
  include_technical?: boolean;
}): Promise<PropertyCatalogResponseV2> {
  const query = buildQuery({
    q: params?.q ?? null,
    status: params?.status ?? null,
    kind: params?.kind ?? null,
    include_technical: params?.include_technical ?? false
  });
  return apiGet<PropertyCatalogResponseV2>(`/v2/properties/catalog${query}`);
}

export async function updatePropertyCatalogV2(
  propertyId: number,
  payload: {
    display_label?: string;
    status?: "stable" | "emerging" | "deprecated";
    include_technical?: boolean;
  }
): Promise<PropertyCatalogRowV2> {
  const query = buildQuery({ include_technical: payload.include_technical ?? false });
  return apiPatch<PropertyCatalogRowV2>(`/v2/properties/catalog/${propertyId}${query}`, payload);
}

export async function getClaimExplainV2(
  claimIndexId: number,
  params?: { include_technical?: boolean }
): Promise<UnifiedClaimExplainV2> {
  const query = buildQuery({ include_technical: params?.include_technical ?? false });
  return apiGet<UnifiedClaimExplainV2>(`/v2/claims/${claimIndexId}/explain${query}`);
}

export async function searchV2(params: {
  q: string;
  conversation_id?: string;
  type_label?: string;
  space_id?: number;
  page_id?: number;
  include_technical?: boolean;
}): Promise<SearchV2Response> {
  const query = buildQuery({
    q: params.q,
    conversation_id: params.conversation_id ?? null,
    type_label: params.type_label ?? null,
    space_id: params.space_id ?? null,
    page_id: params.page_id ?? null,
    include_technical: params.include_technical ?? false
  });
  return apiGet<SearchV2Response>(`/v2/search${query}`);
}

export function warmWorkspaceApi(): Promise<void> {
  if (appWarmupPromise) {
    return appWarmupPromise;
  }

  appWarmupPromise = Promise.allSettled([
    getConversations({ limit: 20, offset: 0 }),
    getConversations({ limit: 200, offset: 0 }),
    getSpacesV2(),
    getRecentEntities(12),
    getLibraryItemsV2({ limit: 25, offset: 0, sort: "last_active", order: "desc" }),
    getPropertiesCatalogV2()
  ]).then(() => undefined);

  return appWarmupPromise;
}

export type WorkspaceSpaceRead = {
  id: number;
  slug: string;
  name: string;
  description: string | null;
  collection_count: number;
  row_count: number;
  created_at: string;
  updated_at: string;
};

export type WorkspaceCollectionRead = {
  id: number;
  pod_id: number;
  parent_id: number | null;
  kind: string;
  slug: string;
  name: string;
  description: string | null;
  is_auto_generated: boolean;
  sort_order: number;
  column_count: number;
  row_count: number;
  pending_suggestion_count: number;
  has_pending_suggestions: boolean;
  updated_at: string;
};

export type WorkspaceColumnRead = {
  id: number;
  collection_id: number;
  key: string;
  label: string;
  data_type: string;
  kind: string;
  sort_order: number;
  required: boolean;
  is_relation: boolean;
  relation_target_collection_id: number | null;
  origin: string;
  planner_locked: boolean;
  user_locked: boolean;
  enrichment_policy_json: Record<string, unknown>;
  coverage_count: number;
  coverage_ratio: number;
};

export type WorkspaceSourceRead = {
  id: number;
  source_kind: string;
  title: string | null;
  uri: string | null;
  snippet: string | null;
  confidence: number | null;
  created_at: string;
};

export type WorkspaceCellSuggestionRead = {
  id: number;
  suggested_display_value: string | null;
  source_kind: string;
  confidence: number | null;
  status: string;
  sources: WorkspaceSourceRead[];
};

export type WorkspaceCellRead = {
  id: number | null;
  column_id: number;
  column_key: string;
  label: string;
  data_type: string;
  value_json: unknown;
  display_value: string | null;
  source_kind: string | null;
  confidence: number | null;
  status: string | null;
  edited_by_user: boolean;
  last_verified_at: string | null;
  sources: WorkspaceSourceRead[];
  pending_suggestion_count: number;
  pending_suggestions: WorkspaceCellSuggestionRead[];
};

export type WorkspaceRowRead = {
  id: number;
  collection_id: number;
  entity_id: number;
  primary_entity_id: number | null;
  title: string;
  summary: string | null;
  detail_blurb: string | null;
  sort_order: number;
  updated_at: string;
  cells: WorkspaceCellRead[];
};

export type WorkspaceRowRelationRead = {
  id: number;
  relation_label: string;
  direction: string;
  other_row_id: number;
  other_row_title: string;
  source_kind: string;
  confidence: number | null;
  status: string;
  sources: WorkspaceSourceRead[];
  suggested: boolean;
};

export type WorkspaceRowDetailRead = {
  id: number;
  collection_id: number;
  collection_name: string;
  collection_slug: string;
  entity_id: number;
  primary_entity_id: number | null;
  title: string;
  summary: string | null;
  detail_blurb: string | null;
  notes_markdown: string | null;
  sort_order: number;
  updated_at: string;
  cells: WorkspaceCellRead[];
  relations: WorkspaceRowRelationRead[];
  pending_relation_suggestion_count: number;
};

export type WorkspaceRowsResponse = {
  collection: WorkspaceCollectionRead;
  columns: WorkspaceColumnRead[];
  rows: WorkspaceRowRead[];
  total: number;
  limit: number;
  offset: number;
  pending_suggestion_count: number;
};

export type WorkspaceOverviewResponse = {
  space: WorkspaceSpaceRead;
  collections: WorkspaceCollectionRead[];
};

export type WorkspaceCatalogRow = {
  collection_id: number;
  collection_name: string;
  collection_slug: string;
  space_id: number;
  space_name: string;
  space_slug: string;
  row: WorkspaceRowRead;
};

export type WorkspaceLibraryResponse = {
  items: WorkspaceCatalogRow[];
  total: number;
  limit: number;
  offset: number;
};

export type WorkspacePropertyCatalogRow = {
  id: number;
  collection_id: number;
  collection_name: string;
  collection_slug: string;
  space_id: number;
  space_name: string;
  key: string;
  label: string;
  data_type: string;
  kind: string;
  origin: string;
  planner_locked: boolean;
  user_locked: boolean;
  coverage_count: number;
  row_count: number;
  coverage_ratio: number;
  updated_at: string;
};

export type WorkspacePropertyCatalogResponse = {
  items: WorkspacePropertyCatalogRow[];
  total: number;
};

export type WorkspaceSyncRunRead = {
  conversation_id: string;
  pod_id: number;
  planner_run_id: number | null;
  enrichment_run_id: number | null;
  collections_upserted: number;
  rows_upserted: number;
  values_upserted: number;
  relations_upserted: number;
};

export type WorkspaceEnrichmentRunRead = {
  id: number;
  pod_id: number;
  conversation_id: string | null;
  collection_id: number | null;
  collection_item_id: number | null;
  requested_by: string;
  run_kind: string;
  status: string;
  stage: string;
  error_message: string | null;
  summary_json: Record<string, unknown>;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
};

export type WorkspaceSuggestionReviewResult = {
  applied: number;
  rejected: number;
};

export async function getWorkspaceSpacesV3(): Promise<WorkspaceSpaceRead[]> {
  return apiGet("/v3/spaces");
}

export async function createWorkspaceSpaceV3(payload: {
  name: string;
  description?: string | null;
}): Promise<WorkspaceSpaceRead> {
  return apiPost("/v3/spaces", payload);
}

export async function updateWorkspaceSpaceV3(
  spaceId: number,
  payload: { name?: string; description?: string | null }
): Promise<WorkspaceSpaceRead> {
  return apiPatch(`/v3/spaces/${spaceId}`, payload);
}

export async function deleteWorkspaceSpaceV3(spaceId: number): Promise<{ space_id: number; deleted: boolean }> {
  return apiDelete(`/v3/spaces/${spaceId}`);
}

export async function getWorkspaceOverviewV3(spaceId: number): Promise<WorkspaceOverviewResponse> {
  return apiGet(`/v3/spaces/${spaceId}/workspace`);
}

export async function createWorkspaceCollectionV3(
  spaceId: number,
  payload: { name: string; description?: string | null }
): Promise<WorkspaceCollectionRead> {
  return apiPost(`/v3/spaces/${spaceId}/collections`, payload);
}

export async function updateWorkspaceCollectionV3(
  collectionId: number,
  payload: { name?: string; description?: string | null }
): Promise<WorkspaceCollectionRead> {
  return apiPatch(`/v3/collections/${collectionId}`, payload);
}

export async function deleteWorkspaceCollectionV3(
  collectionId: number
): Promise<{ collection_id: number; deleted: boolean }> {
  return apiDelete(`/v3/collections/${collectionId}`);
}

export async function createWorkspaceColumnV3(
  collectionId: number,
  payload: { label: string; data_type?: string }
): Promise<WorkspaceColumnRead> {
  return apiPost(`/v3/collections/${collectionId}/columns`, payload);
}

export async function updateWorkspaceColumnV3(
  columnId: number,
  payload: { label?: string; sort_order?: number; required?: boolean; user_locked?: boolean }
): Promise<WorkspaceColumnRead> {
  return apiPatch(`/v3/columns/${columnId}`, payload);
}

export async function deleteWorkspaceColumnV3(
  columnId: number
): Promise<{ column_id: number; deleted: boolean }> {
  return apiDelete(`/v3/columns/${columnId}`);
}

export async function getWorkspaceRowsV3(params: {
  collection_id: number;
  limit?: number;
  offset?: number;
  q?: string;
}): Promise<WorkspaceRowsResponse> {
  return apiGet(
    `/v3/collections/${params.collection_id}/rows${buildQuery({
      limit: params.limit,
      offset: params.offset,
      q: params.q
    })}`
  );
}

export async function createWorkspaceRowV3(
  collectionId: number,
  payload: { entity_id: number }
): Promise<WorkspaceRowDetailRead> {
  return apiPost(`/v3/collections/${collectionId}/rows`, payload);
}

export async function updateWorkspaceRowV3(
  rowId: number,
  payload: {
    title?: string;
    summary?: string | null;
    detail_blurb?: string | null;
    notes_markdown?: string | null;
    sort_order?: number;
  }
): Promise<WorkspaceRowDetailRead> {
  return apiPatch(`/v3/collection-rows/${rowId}`, payload);
}

export async function deleteWorkspaceRowV3(rowId: number): Promise<{ row_id: number; deleted: boolean }> {
  return apiDelete(`/v3/collection-rows/${rowId}`);
}

export async function updateWorkspaceCellV3(
  rowId: number,
  columnId: number,
  payload: { display_value?: string | null; value_json?: unknown; status?: string | null }
): Promise<WorkspaceRowDetailRead> {
  return apiPatch(`/v3/collection-rows/${rowId}/values/${columnId}`, payload);
}

export async function getWorkspaceRowV3(rowId: number): Promise<WorkspaceRowDetailRead> {
  return apiGet(`/v3/collection-rows/${rowId}`);
}

export async function getWorkspaceLibraryV3(params?: {
  limit?: number;
  offset?: number;
  q?: string;
  space_id?: number;
  collection_id?: number;
}): Promise<WorkspaceLibraryResponse> {
  return apiGet(
    `/v3/library${buildQuery({
      limit: params?.limit,
      offset: params?.offset,
      q: params?.q,
      space_id: params?.space_id,
      collection_id: params?.collection_id
    })}`
  );
}

export async function getWorkspacePropertiesV3(params?: {
  space_id?: number;
}): Promise<WorkspacePropertyCatalogResponse> {
  return apiGet(`/v3/properties${buildQuery({ space_id: params?.space_id })}`);
}

export async function runWorkspaceSyncV3(conversationId: string): Promise<WorkspaceSyncRunRead> {
  return apiPost(`/v3/conversations/${encodeURIComponent(conversationId)}/workspace-sync`);
}

export async function enrichWorkspaceRowV3(
  rowId: number,
  options?: { include_sources?: boolean }
): Promise<WorkspaceEnrichmentRunRead> {
  return apiPost(
    `/v3/collection-rows/${rowId}/enrich${buildQuery({ include_sources: options?.include_sources })}`
  );
}

export async function enrichWorkspaceSpaceV3(
  spaceId: number,
  options?: { include_sources?: boolean }
): Promise<WorkspaceEnrichmentRunRead> {
  return apiPost(
    `/v3/spaces/${spaceId}/enrich${buildQuery({ include_sources: options?.include_sources })}`
  );
}

export async function enrichWorkspaceCollectionV3(
  collectionId: number,
  options?: { include_sources?: boolean }
): Promise<WorkspaceEnrichmentRunRead> {
  return apiPost(
    `/v3/collections/${collectionId}/enrich${buildQuery({ include_sources: options?.include_sources })}`
  );
}

export async function getWorkspaceEnrichmentRunV3(runId: number): Promise<WorkspaceEnrichmentRunRead> {
  return apiGet(`/v3/enrichment-runs/${runId}`);
}

export async function getLatestWorkspaceEnrichmentRunForSpaceV3(
  spaceId: number
): Promise<WorkspaceEnrichmentRunRead | null> {
  return apiGet(`/v3/spaces/${spaceId}/enrichment/latest`);
}

export async function acceptWorkspaceCollectionSuggestionsV3(
  collectionId: number
): Promise<WorkspaceSuggestionReviewResult> {
  return apiPost(`/v3/collections/${collectionId}/suggestions/accept`);
}

export async function rejectWorkspaceCollectionSuggestionsV3(
  collectionId: number
): Promise<WorkspaceSuggestionReviewResult> {
  return apiPost(`/v3/collections/${collectionId}/suggestions/reject`);
}

export async function acceptWorkspaceGraphSuggestionsV3(
  scopeKey: string
): Promise<WorkspaceSuggestionReviewResult> {
  return apiPost(`/v3/graph/scopes/${encodeURIComponent(scopeKey)}/suggestions/accept`);
}

export async function rejectWorkspaceGraphSuggestionsV3(
  scopeKey: string
): Promise<WorkspaceSuggestionReviewResult> {
  return apiPost(`/v3/graph/scopes/${encodeURIComponent(scopeKey)}/suggestions/reject`);
}
