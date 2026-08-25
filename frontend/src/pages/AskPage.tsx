import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { ErrorNotice, SourceDrawer } from "../components/Common";
import { ChatComposer } from "../components/ask/ChatComposer";
import { ChatFeed } from "../components/ask/ChatFeed";
import { ChatWorkspace } from "../components/ask/ChatWorkspace";
import { SourcePanel, type SourcePanelTab } from "../components/ask/SourcePanel";
import { StreamingTurn, type PendingTurn } from "../components/ask/StreamingTurn";
import { ProductShell } from "../components/product/ProductShell";
import type { AuthUser, ChatMessage, ChatSession, Citation, DocumentPipeline } from "../types";

function newClientTurnId() {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-0000-4000-8000-${Math.random().toString(16).slice(2).padEnd(12, "0").slice(0, 12)}`;
}

export function AskPage({ user, onLogout }: { user: AuthUser; onLogout: () => void }) {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [sessionsCursor, setSessionsCursor] = useState<string | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [beforeSequence, setBeforeSequence] = useState<number | null>(null);
  const [documents, setDocuments] = useState<DocumentPipeline[]>([]);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [pending, setPending] = useState<PendingTurn | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);
  const [evidenceCitations, setEvidenceCitations] = useState<Citation[]>([]);
  const [drawerCitation, setDrawerCitation] = useState<Citation | null>(null);
  const [sourceOpen, setSourceOpen] = useState(() => typeof window.matchMedia === "function" ? window.matchMedia("(min-width: 1280px)").matches : true);
  const [sourceTab, setSourceTab] = useState<SourcePanelTab>("scope");

  const refreshSessions = useCallback(async () => {
    const page = await api.chatSessions();
    setSessions(page.data);
    setSessionsCursor(page.next_cursor);
    return page.data;
  }, []);

  const loadMessages = useCallback(async (sessionId: string) => {
    const page = await api.chatMessages(sessionId);
    setMessages(page.data);
    setBeforeSequence(page.next_before_sequence);
  }, []);

  useEffect(() => {
    void Promise.all([api.documents().then((items) => {
      setDocuments(items);
      setSelectedDocumentIds(items.filter((item) => item.index_count > 0).map((item) => item.document_id));
    }), refreshSessions()])
      .then(([, items]) => setActiveSessionId((current) => current ?? items[0]?.id ?? null))
      .catch(setError);
  }, [refreshSessions]);

  useEffect(() => {
    setMessages([]);
    setBeforeSequence(null);
    setActiveCitation(null);
    if (activeSessionId) void loadMessages(activeSessionId).catch(setError);
  }, [activeSessionId, loadMessages]);

  const createSession = async () => {
    const created = await api.createChatSession();
    setSessions((items) => [created, ...items]);
    setActiveSessionId(created.id);
    setMessages([]);
    return created.id;
  };

  const submit = async (explicitQuery = query, explicitDocumentIds = selectedDocumentIds) => {
    const clean = explicitQuery.trim();
    const indexedDocumentIds = documents.filter((item) => item.index_count > 0).map((item) => item.document_id);
    if (!clean || pending || (indexedDocumentIds.length > 0 && explicitDocumentIds.length === 0)) return;
    const allSelected = indexedDocumentIds.length === explicitDocumentIds.length && indexedDocumentIds.every((id) => explicitDocumentIds.includes(id));
    try {
      setError(null);
      const sessionId = activeSessionId ?? await createSession();
      setActiveSessionId(sessionId);
      setPending({ clientTurnId: newClientTurnId(), query: clean, documentIds: allSelected ? null : explicitDocumentIds });
      setQuery("");
    } catch (value) { setError(value); }
  };

  const rename = async (session: ChatSession) => {
    const title = window.prompt("Conversation title", session.title)?.trim();
    if (!title || title === session.title) return;
    try {
      const updated = await api.renameChatSession(session.id, title);
      setSessions((items) => items.map((item) => item.id === updated.id ? updated : item));
    } catch (value) { setError(value); }
  };

  const remove = async (session: ChatSession) => {
    if (!window.confirm(`Delete “${session.title}” and its history?`)) return;
    try {
      await api.deleteChatSession(session.id);
      const remaining = sessions.filter((item) => item.id !== session.id);
      setSessions(remaining);
      if (activeSessionId === session.id) setActiveSessionId(remaining[0]?.id ?? null);
    } catch (value) { setError(value); }
  };

  const settleTurn = useCallback(async () => {
    setPending(null);
    if (activeSessionId) await loadMessages(activeSessionId).catch(setError);
    await refreshSessions().catch(setError);
  }, [activeSessionId, loadMessages, refreshSessions]);

  const loadOlderMessages = async () => {
    if (!activeSessionId || beforeSequence == null) return;
    try {
      const page = await api.chatMessages(activeSessionId, beforeSequence);
      setMessages((items) => [...page.data, ...items]);
      setBeforeSequence(page.next_before_sequence);
    } catch (value) { setError(value); }
  };

  const inspect = (citation: Citation) => {
    setActiveCitation(citation);
    setEvidenceCitations((items) => items.some((item) => item.source_id === citation.source_id && item.chunk_id === citation.chunk_id && item.snapshot_id === citation.snapshot_id) ? items : [citation]);
    setSourceTab("evidence");
    setSourceOpen(true);
  };

  const inspectSources = (citations: Citation[]) => {
    setEvidenceCitations(citations);
    setActiveCitation(citations[0] ?? null);
    setSourceTab("evidence");
    setSourceOpen(true);
  };

  const openScope = () => { setSourceTab("scope"); setSourceOpen(true); };
  const openEvidence = () => { setSourceTab("evidence"); setSourceOpen(true); };

  const retry = (message: ChatMessage) => {
    const userMessage = [...messages].reverse().find((item) => item.role === "USER" && item.turn_id === message.turn_id);
    if (userMessage) void submit(userMessage.content, selectedDocumentIds);
  };

  const loadOlderSessions = () => {
    if (!sessionsCursor) return;
    void api.chatSessions(sessionsCursor).then((page) => {
      setSessions((items) => [...items, ...page.data]);
      setSessionsCursor(page.next_cursor);
    }).catch(setError);
  };

  const activeSession = sessions.find((item) => item.id === activeSessionId);
  const indexedDocuments = documents.filter((item) => item.index_count > 0);
  const allDocumentsSelected = indexedDocuments.length === selectedDocumentIds.length && indexedDocuments.every((item) => selectedDocumentIds.includes(item.document_id));
  const scopeLabel = allDocumentsSelected ? "All Indexed Documents" : selectedDocumentIds.length === 1 ? "1 Document" : `${selectedDocumentIds.length} Documents`;
  const scopeValid = indexedDocuments.length === 0 || selectedDocumentIds.length > 0;
  const toggleDocument = (documentId: string) => setSelectedDocumentIds((items) => items.includes(documentId) ? items.filter((id) => id !== documentId) : [...items, documentId]);
  const toggleAllDocuments = () => setSelectedDocumentIds(allDocumentsSelected ? [] : indexedDocuments.map((item) => item.document_id));
  return <>
    <ProductShell
      sidebar={{ user, sessions, activeSessionId, hasOlderSessions: Boolean(sessionsCursor), onSelectSession: setActiveSessionId, onCreateSession: async () => { await createSession().catch(setError); }, onRenameSession: rename, onDeleteSession: remove, onLoadOlderSessions: loadOlderSessions, onLogout }}
      rightOpen={sourceOpen}
      onCloseRight={() => setSourceOpen(false)}
      rightPanel={<SourcePanel tab={sourceTab} onTabChange={setSourceTab} documents={documents} selectedDocumentIds={selectedDocumentIds} activeCitation={activeCitation} evidenceCitations={evidenceCitations} onToggleDocument={toggleDocument} onSelectAll={toggleAllDocuments} onSelectCitation={inspect} onOpenCitationDetail={setDrawerCitation} onClose={() => setSourceOpen(false)} />}
    >
      <>
        {error ? <div className="fixed left-1/2 top-3 z-50 w-[min(560px,90vw)] -translate-x-1/2"><ErrorNotice error={error} /></div> : null}
        <ChatWorkspace
          title={activeSession?.title === "New conversation" ? "New Inquiry" : activeSession?.title ?? "New Inquiry"}
          scopeLabel={scopeLabel}
          onOpenScope={openScope}
          onOpenEvidence={openEvidence}
          feed={<ChatFeed messages={messages} hasOlder={beforeSequence != null} onLoadOlder={() => void loadOlderMessages()} onCitation={inspect} onSources={inspectSources} onRetry={retry} pendingTurn={pending && activeSessionId ? <StreamingTurn key={pending.clientTurnId} sessionId={activeSessionId} turn={pending} onCitation={inspect} onSettled={settleTurn} /> : undefined} />}
          composer={<ChatComposer query={query} pending={Boolean(pending)} scopeValid={scopeValid} onQueryChange={setQuery} onSubmit={() => void submit()} onOpenScope={openScope} />}
        />
      </>
    </ProductShell>
    <SourceDrawer source={drawerCitation ? { chunkId: drawerCitation.chunk_id, sourceId: drawerCitation.source_id } : null} citation={drawerCitation} onClose={() => setDrawerCitation(null)} />
  </>;
}
