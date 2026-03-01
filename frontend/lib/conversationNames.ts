"use client";

const CONVERSATION_NAME_STORAGE_KEY = "librarian.chat.names.v1";

type ConversationNameMap = Record<string, string>;

function clampTitleWords(value: string): string {
  const normalized = value.replace(/\s+/g, " ").trim();
  if (!normalized) {
    return "";
  }
  const maxWords = 4;
  const words = normalized.split(" ").filter(Boolean);
  const short = words.slice(0, maxWords).join(" ");
  const maxLength = 64;
  if (short.length <= maxLength) {
    return short;
  }
  const clipped = short.slice(0, maxLength).trimEnd();
  return `${clipped}...`;
}

function readNameMapRaw(): ConversationNameMap {
  if (typeof window === "undefined") {
    return {};
  }
  try {
    const parsed = JSON.parse(
      window.localStorage.getItem(CONVERSATION_NAME_STORAGE_KEY) ?? "{}"
    ) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return {};
    }
    const next: ConversationNameMap = {};
    Object.entries(parsed).forEach(([key, value]) => {
      if (!key.trim() || typeof value !== "string" || !value.trim()) {
        return;
      }
      const title = clampTitleWords(value);
      if (!title) {
        return;
      }
      next[key] = title;
    });
    return next;
  } catch {
    return {};
  }
}

function writeNameMapRaw(nextMap: ConversationNameMap) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(CONVERSATION_NAME_STORAGE_KEY, JSON.stringify(nextMap));
}

function titleFromFirstMessage(content: string): string | null {
  const capped = clampTitleWords(content);
  if (!capped) {
    return null;
  }
  return capped;
}

export function readConversationNames(): ConversationNameMap {
  return readNameMapRaw();
}

export function getConversationName(conversationId: string): string | null {
  const cleanConversationId = conversationId.trim();
  if (!cleanConversationId) {
    return null;
  }
  const map = readNameMapRaw();
  return map[cleanConversationId] ?? null;
}

export function ensureConversationNameFromFirstText(
  conversationId: string,
  firstText: string
): string | null {
  const cleanConversationId = conversationId.trim();
  if (!cleanConversationId) {
    return null;
  }
  const map = readNameMapRaw();
  if (map[cleanConversationId]) {
    return map[cleanConversationId];
  }
  const generated = titleFromFirstMessage(firstText);
  if (!generated) {
    return null;
  }
  map[cleanConversationId] = generated;
  writeNameMapRaw(map);
  return generated;
}

export function removeConversationName(conversationId: string) {
  const cleanConversationId = conversationId.trim();
  if (!cleanConversationId) {
    return;
  }
  const map = readNameMapRaw();
  if (!map[cleanConversationId]) {
    return;
  }
  delete map[cleanConversationId];
  writeNameMapRaw(map);
}
