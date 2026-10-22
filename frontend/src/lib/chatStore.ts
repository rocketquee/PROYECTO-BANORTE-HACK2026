"use client";

/**
 * Global chat store (BUG-002).
 *
 * Conversation state lives outside React so it survives navigation between
 * screens, and is persisted to localStorage so it survives page reloads.
 * The sidebar uses the same store for the conversation history.
 */
import { useSyncExternalStore } from "react";
import type { ChatResponse, UISpec } from "@/types/contract";
import { sanitizeUserText } from "@/lib/chatSecurity.mjs";

export interface ChatMsg {
  role: "user" | "assistant" | "system";
  text?: string;
  resp?: ChatResponse;
  error?: string;
}

export interface Conversation {
  id: string;
  title: string;
  createdAt: number;
  messages: ChatMsg[];
  history: { role: "user" | "assistant"; content: string }[];
}

interface ChatState {
  conversations: Conversation[];
  activeId: string;
  loading: boolean;
  /** Result opened in "expanded detail" (right panel): message key + specs. */
  detail: UISpec[] | null;
  detailKey: string | null;
}

const STORAGE_KEY = "baf.conversations.v1";

function makeId(): string {
  return `c_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

function newConversation(): Conversation {
  return { id: makeId(), title: "Nueva conversación", createdAt: Date.now(),
           messages: [], history: [] };
}

function initialState(): ChatState {
  const initialConversation: Conversation = {
    id: "initial",
    title: "Nueva conversación",
    createdAt: 0,
    messages: [],
    history: [],
  };
  const fallback: ChatState = {
    conversations: [initialConversation],
    activeId: initialConversation.id,
    loading: false,
    detail: null,
    detailKey: null,
  };
  return fallback;
}

let state: ChatState = initialState();
const listeners = new Set<() => void>();

function persist() {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch { /* storage full or unavailable */ }
}

function setState(patch: Partial<ChatState>) {
  state = { ...state, ...patch };
  persist();
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot() {
  return state;
}

function hydrateFromStorage() {
  if (typeof window === "undefined") return;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw) as ChatState;
    if (!parsed.conversations?.length) return;
    state = {
      ...state,
      ...parsed,
      conversations: parsed.conversations.map((conversation) => ({
        ...conversation,
        messages: conversation.messages.map((message) =>
          message.role === "user" && message.text
            ? { ...message, text: sanitizeUserText(message.text) }
            : message),
        history: conversation.history.map((entry) => ({
          ...entry,
          content: entry.role === "user" ? sanitizeUserText(entry.content) : entry.content,
        })),
      })),
      loading: false,
      detail: null,
      detailKey: null,
    };
    listeners.forEach((listener) => listener());
  } catch {
    return;
  }
}

export function useChatStore(): ChatState {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}

export function activeConversation(s: ChatState = state): Conversation {
  return s.conversations.find((c) => c.id === s.activeId) ?? s.conversations[0];
}

export const chatActions = {
  hydrate: hydrateFromStorage,

  addMessage(msg: ChatMsg) {
    const conv = activeConversation();
    const safeMsg = msg.role === "user" && msg.text
      ? { ...msg, text: sanitizeUserText(msg.text) }
      : msg;
    const conversations = state.conversations.map((c) =>
      c.id === conv.id
        ? {
            ...c,
            messages: [...c.messages, safeMsg],
            history:
              safeMsg.role === "user" && safeMsg.text
                ? [...c.history, { role: "user" as const, content: safeMsg.text }]
                : safeMsg.role === "assistant" && safeMsg.resp
                  ? [...c.history, { role: "assistant" as const, content: safeMsg.resp.message }]
                  : c.history,
            title:
              c.messages.length === 0 && safeMsg.role === "user" && safeMsg.text
                ? safeMsg.text.slice(0, 40) + (safeMsg.text.length > 40 ? "…" : "")
                : c.title,
          }
        : c
    );
    setState({ conversations });
  },

  setLoading(loading: boolean) {
    setState({ loading });
  },

  setDetail(detail: UISpec[] | null, detailKey: string | null = null) {
    setState({ detail, detailKey });
  },

  updateMessage(index: number, updater: (msg: ChatMsg) => ChatMsg) {
    const conv = activeConversation();
    const conversations = state.conversations.map((c) =>
      c.id === conv.id
        ? { ...c, messages: c.messages.map((m, i) => (i === index ? updater(m) : m)) }
        : c
    );
    setState({ conversations });
  },

  newConversation() {
    const conv = newConversation();
    setState({ conversations: [conv, ...state.conversations], activeId: conv.id,
               detail: null });
  },

  selectConversation(id: string) {
    setState({ activeId: id, detail: null });
  },

  deleteConversation(id: string) {
    const remaining = state.conversations.filter((c) => c.id !== id);
    if (remaining.length === 0) {
      const conv = newConversation();
      setState({ conversations: [conv], activeId: conv.id, detail: null });
      return;
    }
    setState({
      conversations: remaining,
      activeId: state.activeId === id ? remaining[0].id : state.activeId,
      detail: null,
    });
  },

  clearAll() {
    const conv = newConversation();
    setState({ conversations: [conv], activeId: conv.id, detail: null });
  },
};
