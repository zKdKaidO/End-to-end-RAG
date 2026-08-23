import { useCallback, useEffect, useRef, useState } from "react";
import { BookOpen, Edit3, MessageSquarePlus, PanelRightClose, Square, Trash2 } from "lucide-react";
import { Group, Panel, Separator, usePanelRef } from "react-resizable-panels";
import { api, streamChatTurn } from "../api/client";
import { CitedAnswer, EmptyState, ErrorNotice, PageHeading, SourceDrawer, SourceList, StatusBadge } from "../components/Common";
import { useBufferedStream } from "../hooks/useBufferedStream";
import { useMediaQuery } from "../hooks/useMediaQuery";
import type { ChatMessage, ChatSession, Citation, DocumentPipeline, GenerationResult } from "../types";

interface PendingTurn { clientTurnId: string; query: string; documentId: string; }

function newClientTurnId() {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-0000-4000-8000-${Math.random().toString(16).slice(2).padEnd(12, "0").slice(0, 12)}`;
}

export function AskPage() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [sessionsCursor, setSessionsCursor] = useState<string | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [beforeSequence, setBeforeSequence] = useState<number | null>(null);
  const [documents, setDocuments] = useState<DocumentPipeline[]>([]);
  const [documentId, setDocumentId] = useState("");
  const [query, setQuery] = useState("");
  const [pending, setPending] = useState<PendingTurn | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);
  const [mobileSource, setMobileSource] = useState<Citation | null>(null);
  const sourcePanel = usePanelRef();
  const isDesktop = useMediaQuery("(min-width: 900px)");

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
    void Promise.all([api.documents().then(setDocuments), refreshSessions()])
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

  const submit = async (explicitQuery = query, explicitDocument = documentId) => {
    const clean = explicitQuery.trim();
    if (!clean || pending) return;
    try {
      setError(null);
      const sessionId = activeSessionId ?? await createSession();
      setActiveSessionId(sessionId);
      setPending({ clientTurnId: newClientTurnId(), query: clean, documentId: explicitDocument });
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
    if (!isDesktop) setMobileSource(citation);
    else sourcePanel.current?.expand();
  };

  const retry = (message: ChatMessage) => {
    const user = [...messages].reverse().find((item) => item.role === "USER" && item.turn_id === message.turn_id);
    if (user) void submit(user.content, documentId); // Explicit retry always gets a new client_turn_id.
  };

  const activeSession = sessions.find((item) => item.id === activeSessionId);
  const transcript = (
    <section className="chat-transcript" aria-label="Conversation history">
      {beforeSequence != null ? <button className="compact-button load-history" onClick={loadOlderMessages}>Load older messages</button> : null}
      {!messages.length && !pending ? <EmptyState icon={<BookOpen size={19} />}>Ask a question to begin a persistent, traceable research session.</EmptyState> : null}
      {messages.map((message) => message.role === "USER" ? (
        <article className="chat-message user-message" key={message.id}><span className="eyebrow">Question</span><p>{message.content}</p></article>
      ) : <HistoricalAnswer key={message.id} message={message} onCitation={inspect} onRetry={() => retry(message)} />)}
      {pending && activeSessionId ? <StreamingTurn key={pending.clientTurnId} sessionId={activeSessionId} turn={pending} onCitation={inspect} onSettled={settleTurn} /> : null}
    </section>
  );

  return (
    <div className="page ask-page persistent-ask">
      <PageHeading eyebrow="Grounded legal research" title="Ask the corpus" description="Persistent answers retain immutable evidence snapshots. Previous turns are never injected into retrieval or generation." />
      <ErrorNotice error={error} />
      <div className="chat-layout">
        <aside className="conversation-rail" aria-label="Conversations">
          <button className="primary new-conversation" onClick={() => void createSession().catch(setError)}><MessageSquarePlus size={15} /> New conversation</button>
          <div className="conversation-list">
            {sessions.map((session) => <div className={`conversation-item ${session.id === activeSessionId ? "active" : ""}`} key={session.id}>
              <button className="conversation-open" onClick={() => setActiveSessionId(session.id)}><strong>{session.title}</strong><small>{session.message_count} messages</small></button>
              <button className="icon-button" aria-label={`Rename ${session.title}`} onClick={() => void rename(session)}><Edit3 size={13} /></button>
              <button className="icon-button" aria-label={`Delete ${session.title}`} onClick={() => void remove(session)}><Trash2 size={13} /></button>
            </div>)}
          </div>
          {sessionsCursor ? <button className="compact-button" onClick={() => api.chatSessions(sessionsCursor).then((page) => { setSessions((items) => [...items, ...page.data]); setSessionsCursor(page.next_cursor); }).catch(setError)}>Older conversations</button> : null}
        </aside>
        <div className="chat-main">
          <section className="panel query-panel" aria-label="Research query">
            <div className="active-conversation"><span className="eyebrow">Conversation</span><strong>{activeSession?.title ?? "Not yet created"}</strong></div>
            <label className="query-field"><span>Question</span><textarea value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if ((event.metaKey || event.ctrlKey) && event.key === "Enter") void submit(); }} rows={3} placeholder="Ask a Vietnamese legal question…" /></label>
            <div className="query-options"><label>Corpus scope<select value={documentId} onChange={(event) => setDocumentId(event.target.value)}><option value="">All indexed documents</option>{documents.filter((item) => item.index_count).map((item) => <option key={item.document_id} value={item.document_id}>{item.filename}</option>)}</select></label><button className="primary ask-button" onClick={() => void submit()} disabled={!query.trim() || Boolean(pending)}>Ask</button></div>
            <small className="keyboard-hint">Ctrl/⌘ + Enter to submit · history is server-backed</small>
          </section>
          <section className="research-workspace panel">
            {isDesktop ? <Group orientation="horizontal" className="answer-split"><Panel id="answer" defaultSize="70" minSize="48">{transcript}</Panel><Separator className="resize-handle" aria-label="Resize answer and sources" /><Panel id="sources" panelRef={sourcePanel} defaultSize="30" minSize="22" collapsible collapsedSize={0}><aside className="source-panel" aria-label="Answer sources"><header><div><span className="eyebrow">Sources</span><h2>{activeCitation ? "Historical snapshot" : "Select a citation"}</h2></div><button className="icon-button" aria-label="Collapse sources" onClick={() => sourcePanel.current?.collapse()}><PanelRightClose size={17} /></button></header><SourceList citations={activeCitation ? [activeCitation] : []} activeSourceId={activeCitation?.source_id} onInspect={(item) => setMobileSource(item)} /></aside></Panel></Group> : transcript}
          </section>
        </div>
      </div>
      <SourceDrawer source={mobileSource ? { chunkId: mobileSource.chunk_id, sourceId: mobileSource.source_id } : null} citation={mobileSource} onClose={() => setMobileSource(null)} />
    </div>
  );
}

function HistoricalAnswer({ message, onCitation, onRetry }: { message: ChatMessage; onCitation: (citation: Citation) => void; onRetry: () => void }) {
  const terminalFailure = message.delivery_state === "FAILED" || message.delivery_state === "CANCELLED";
  return <article className={`chat-message assistant-message ${terminalFailure ? "incomplete" : ""}`}><header className="answer-toolbar"><div><span className="eyebrow">Historical answer</span><StatusBadge value={message.failure_code === "ORPHANED_STREAM_TIMEOUT" ? "INTERRUPTED" : message.answer_status ?? message.delivery_state} /></div></header>{terminalFailure ? <div className="notice warning"><span>{message.failure_detail_safe ?? "Incomplete response."}</span><button className="compact-button" onClick={onRetry}>Retry</button></div> : null}{message.content ? <CitedAnswer text={message.content} citations={message.citations} onCitation={onCitation} /> : null}{!terminalFailure && message.answer_status === "INSUFFICIENT_EVIDENCE" ? <div className="notice warning">The selected evidence did not support the exact requested fact.</div> : null}{!terminalFailure ? <SourceList citations={message.citations} onInspect={onCitation} /> : null}<footer className="answer-meta"><span>{message.model_id ?? "No model result"}</span><span>{message.prompt_version ?? "—"}</span><span>{message.citations.length} snapshot sources</span></footer></article>;
}

function StreamingTurn({ sessionId, turn, onCitation, onSettled }: { sessionId: string; turn: PendingTurn; onCitation: (citation: Citation) => void; onSettled: () => Promise<void>; }) {
  const [phase, setPhase] = useState("connecting");
  const [result, setResult] = useState<GenerationResult | null>(null);
  const [error, setError] = useState<unknown>(null);
  const controller = useRef<AbortController | null>(null);
  const { visibleText, append, finish, reset, stats } = useBufferedStream();
  useEffect(() => {
    const abortController = new AbortController(); controller.current = abortController; reset();
    void streamChatTurn(sessionId, { client_turn_id: turn.clientTurnId, query: turn.query, document_ids: turn.documentId ? [turn.documentId] : null }, {
      start: () => setPhase("streaming"), delta: append,
      done: (value) => { finish(value.answer_text); setResult(value); setPhase("done"); window.setTimeout(() => void onSettled(), 0); },
      error: (value) => { setError(new Error(String(value.safe_message ?? "Provider stream failed"))); setPhase("error"); window.setTimeout(() => void onSettled(), 0); },
    }, abortController.signal).catch((value: unknown) => { if ((value as Error).name === "AbortError") { setPhase("cancelled"); window.setTimeout(() => void onSettled(), 150); } else { setError(value); setPhase("error"); window.setTimeout(() => void onSettled(), 0); } });
    return () => abortController.abort();
  }, [append, finish, onSettled, reset, sessionId, turn]);
  return <article className="chat-message assistant-message live-message" aria-live="polite"><header className="answer-toolbar"><div><span className="eyebrow">Answer</span><StatusBadge value={result?.status ?? phase} /></div>{["connecting", "streaming"].includes(phase) ? <button className="compact-button" aria-label="Stop generation" onClick={() => controller.current?.abort()}><Square size={13} /> Stop</button> : null}</header><ErrorNotice error={error} />{!visibleText && phase === "connecting" ? <div className="loading">Initializing persistent turn…</div> : null}{!visibleText && phase === "streaming" ? <div className="loading">Preparing the first grounded token…</div> : null}{visibleText ? <CitedAnswer text={visibleText} citations={result?.citations ?? []} onCitation={onCitation} /> : null}{import.meta.env.DEV && stats.incomingDeltas ? <details className="stream-diagnostics"><summary>Streaming diagnostics</summary><span>{stats.incomingDeltas} provider deltas → {stats.visibleCommits} visible commits · {stats.cadenceMs} ms cadence</span></details> : null}</article>;
}
