import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowUp, FileText, LogOut, MessageSquare, PanelLeftClose, PanelLeftOpen, Plus, Search } from "lucide-react";
import { NavLink, useNavigate, useParams } from "react-router-dom";
import { BrowserComputeClient, type LocalAnswerResponse, type LocalCitation, type LocalComputeDocument, type LocalGenerationResult } from "../compute";
import { CitedAnswer, ErrorNotice } from "../components/Common";
import { ZkdWordmark } from "../components/product/ZkdWordmark";
import type { AuthUser, Citation } from "../types";
import "./AskPage.css";

interface AskPageProps { user: AuthUser; onLogout: () => void; }
interface AskSource { document_id: string; filename: string; page_count: number; chunk_count: number; }
interface LocalUserMessage { id: string; kind: "USER"; content: string; }
interface LocalAssistantMessage { id: string; kind: "ASSISTANT"; query: string; documentIds: string[] | null; state: "PENDING" | "COMPLETED" | "FAILED"; result?: LocalGenerationResult; provider?: LocalAnswerResponse["provider"]; citations: Citation[]; error?: unknown; }
type LocalAskMessage = LocalUserMessage | LocalAssistantMessage;

function newMemoryId() { return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-0000-4000-8000-${Math.random().toString(16).slice(2).padEnd(12, "0").slice(0, 12)}`; }
function isQueryable(document: LocalComputeDocument) { return document.preparation_state === "INDEX_READY" && document.index_state === "INDEX_READY"; }
function toAskSource(document: LocalComputeDocument): AskSource { return { document_id: document.document_id, filename: document.original_filename, page_count: document.page_count, chunk_count: document.chunk_count }; }
function safePage(value: unknown): number | null { return typeof value === "number" && Number.isSafeInteger(value) && value > 0 ? value : null; }
function toProductCitation(citation: LocalCitation, sources: AskSource[]): Citation {
  const source = sources.find((item) => item.document_id === citation.document_id);
  return { source_id: citation.source_id, chunk_id: citation.chunk_id, document_id: citation.document_id, metadata_json: citation.metadata_json, provenance_json: citation.provenance_json, document_filename: source?.filename ?? null, page_start: safePage(citation.provenance_json.page_start), page_end: safePage(citation.provenance_json.page_end) };
}

export function AskPage({ user, onLogout }: AskPageProps) {
  const navigate = useNavigate();
  const { sessionId } = useParams<{ sessionId?: string }>();
  const computeRef = useRef<BrowserComputeClient | null>(null);
  const sourceDeviceIdRef = useRef<string | null>(null);
  const sourceCatalogLoadedRef = useRef(false);
  if (!computeRef.current) computeRef.current = new BrowserComputeClient();

  const [messages, setMessages] = useState<LocalAskMessage[]>([]);
  const [documents, setDocuments] = useState<AskSource[]>([]);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const [sourceSearch, setSourceSearch] = useState("");
  const [query, setQuery] = useState("");
  const [pendingMessageId, setPendingMessageId] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);
  const [modelId, setModelId] = useState("Local model");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => window.localStorage.getItem("zkd-sidebar-collapsed") === "1");

  const loadLocalSources = useCallback(async () => {
    const compute = computeRef.current!;
    const session = await compute.connect("answer");
    const localDocuments = (await compute.listDocuments()).filter(isQueryable).map(toAskSource);
    const deviceChanged = sourceDeviceIdRef.current !== null && sourceDeviceIdRef.current !== session.deviceId;
    const initialCatalog = !sourceCatalogLoadedRef.current;
    sourceDeviceIdRef.current = session.deviceId;
    setDocuments(localDocuments);
    setSelectedDocumentIds((current) => initialCatalog || deviceChanged ? localDocuments.map((item) => item.document_id) : current.filter((documentId) => localDocuments.some((item) => item.document_id === documentId)));
    sourceCatalogLoadedRef.current = true;
    if (deviceChanged) { setMessages([]); setActiveCitation(null); setPendingMessageId(null); }
  }, []);

  useEffect(() => { let active = true; void loadLocalSources().catch((value) => active && setError(value)); return () => { active = false; }; }, [loadLocalSources]);
  useEffect(() => { if (sessionId) navigate("/ask", { replace: true }); }, [navigate, sessionId]);
  useEffect(() => { window.localStorage.setItem("zkd-sidebar-collapsed", sidebarCollapsed ? "1" : "0"); }, [sidebarCollapsed]);

  const filteredDocuments = useMemo(() => {
    const needle = sourceSearch.trim().toLocaleLowerCase();
    return needle ? documents.filter((document) => document.filename.toLocaleLowerCase().includes(needle)) : documents;
  }, [documents, sourceSearch]);
  const allDocumentsSelected = documents.length > 0 && documents.every((document) => selectedDocumentIds.includes(document.document_id));
  const selectionRequired = documents.length > 0 && selectedDocumentIds.length === 0;
  const isNewInquiry = messages.length === 0;

  const startNewInquiry = () => { setMessages([]); setPendingMessageId(null); setQuery(""); setError(null); setActiveCitation(null); navigate("/ask"); };
  const submit = async (explicitQuery = query, explicitDocumentIds = selectedDocumentIds) => {
    const clean = explicitQuery.trim();
    if (!clean || pendingMessageId || (documents.length > 0 && explicitDocumentIds.length === 0)) return;
    const documentIds = documents.length === 0 || allDocumentsSelected ? null : explicitDocumentIds;
    const assistantId = newMemoryId();
    setError(null);
    setActiveCitation(null);
    setMessages((current) => [...current, { id: newMemoryId(), kind: "USER", content: clean }, { id: assistantId, kind: "ASSISTANT", query: clean, documentIds, state: "PENDING", citations: [] }]);
    setPendingMessageId(assistantId);
    setQuery("");
    try {
      const response = await computeRef.current!.answer({ query_text: clean, document_ids: documentIds });
      const citations = response.result.citations.map((citation) => toProductCitation(citation, documents));
      setModelId(response.model_id || modelId);
      setMessages((current) => current.map((message) => message.kind === "ASSISTANT" && message.id === assistantId ? { ...message, state: "COMPLETED", result: response.result, provider: response.provider, citations } : message));
    } catch (value) {
      setError(value);
      setMessages((current) => current.map((message) => message.kind === "ASSISTANT" && message.id === assistantId ? { ...message, state: "FAILED", error: value } : message));
    } finally {
      setPendingMessageId((current) => current === assistantId ? null : current);
    }
  };
  const retry = (message: LocalAssistantMessage) => { if (message.state === "FAILED") void submit(message.query, selectedDocumentIds); };
  const toggleDocument = (documentId: string) => { setSelectedDocumentIds((current) => current.includes(documentId) ? current.filter((id) => id !== documentId) : [...current, documentId]); };
  const toggleSelectAll = () => { setSelectedDocumentIds(allDocumentsSelected ? [] : documents.map((document) => document.document_id)); };

  return <div className={`zkd-ask ${sidebarCollapsed ? "zkd-ask--sidebar-collapsed" : ""}`}>
    <aside className="zkd-sidebar" aria-label="zKd AI workspace">
      <div className={`zkd-sidebar-top ${sidebarCollapsed ? "zkd-sidebar-top--collapsed" : ""}`}>
        {!sidebarCollapsed ? <button className="zkd-sidebar-brand-button" type="button" title="zKd AI" onClick={startNewInquiry}><ZkdWordmark /></button> : null}
        <button className="zkd-sidebar-collapse" type="button" aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"} title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"} onClick={() => setSidebarCollapsed((value) => !value)}>{sidebarCollapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}</button>
      </div>
      <button className="zkd-new-button" type="button" title="New inquiry" onClick={startNewInquiry}><Plus size={17} strokeWidth={1.8} />{!sidebarCollapsed ? <span>New</span> : null}</button>
      <nav className="zkd-sidebar-nav" aria-label="Ask workspace navigation">
        <NavLink to="/ask" title="Ask" className={({ isActive }) => `zkd-nav-item ${isActive ? "active" : ""}`}><MessageSquare size={17} strokeWidth={1.8} />{!sidebarCollapsed ? <span>Ask</span> : null}</NavLink>
        <NavLink to="/documents" title="Documents" className={({ isActive }) => `zkd-nav-item ${isActive ? "active" : ""}`}><FileText size={17} strokeWidth={1.8} />{!sidebarCollapsed ? <span>Documents</span> : null}</NavLink>
      </nav>
      <div className="zkd-sidebar-collapsed-space" />
      <div className={`zkd-user ${sidebarCollapsed ? "zkd-user--collapsed" : ""}`}><div className="zkd-user-avatar">{user.email.slice(0, 1).toUpperCase()}</div>{!sidebarCollapsed ? <div className="zkd-user-copy"><strong title={user.email}>{user.email}</strong><span>{user.role}</span></div> : null}<button className="zkd-logout" type="button" aria-label="Sign out" title="Sign out" onClick={onLogout}><LogOut size={15} /></button></div>
    </aside>

    <main className={`zkd-chat ${isNewInquiry ? "zkd-chat--new" : ""}`}>
      {error ? <div className="zkd-error"><ErrorNotice error={error} /></div> : null}
      {isNewInquiry ? <section className="zkd-home"><ZkdWordmark size="hero" /><Composer query={query} modelId={modelId} pending={Boolean(pendingMessageId)} selectionRequired={selectionRequired} variant="hero" onChange={setQuery} onSubmit={() => void submit()} /></section> : <>
        <header className="zkd-chat-header"><span>Conversation</span></header>
        <div className="zkd-transcript"><div className="zkd-transcript-inner">{messages.map((message) => message.kind === "USER" ? <article className="zkd-message zkd-message--user" key={message.id}><div className="zkd-user-bubble">{message.content}</div></article> : <LocalAnswer key={message.id} message={message} onCitation={setActiveCitation} onRetry={() => retry(message)} />)}</div></div>
        <div className="zkd-conversation-composer"><Composer query={query} modelId={modelId} pending={Boolean(pendingMessageId)} selectionRequired={selectionRequired} variant="conversation" onChange={setQuery} onSubmit={() => void submit()} /></div>
      </>}
    </main>

    <aside className="zkd-sources" aria-label="Sources" data-active-source={activeCitation?.source_id}>
      <div className="zkd-sources-header"><h2>Sources</h2><label className={`zkd-select-all ${allDocumentsSelected ? "selected" : ""}`}><input className="zkd-source-native-input" type="checkbox" aria-label="Select All" checked={allDocumentsSelected} onChange={toggleSelectAll} /><span className="zkd-source-radio" aria-hidden="true" /><span>Select all</span></label></div>
      <div className="zkd-source-search"><Search size={14} aria-hidden="true" /><input value={sourceSearch} placeholder="Search sources" aria-label="Search sources" onChange={(event) => setSourceSearch(event.target.value)} /></div>
      <div className="zkd-source-list">{filteredDocuments.map((document) => {
        const selected = selectedDocumentIds.includes(document.document_id);
        return <label className={`zkd-source-item ${selected ? "selected" : ""}`} key={document.document_id}><input className="zkd-source-native-input" type="checkbox" aria-label={`Include ${document.filename}`} checked={selected} onChange={() => toggleDocument(document.document_id)} /><span className="zkd-source-radio" aria-hidden="true" /><div className="zkd-source-copy"><strong title={document.filename}>{document.filename}</strong><span>{document.page_count} pages · {document.chunk_count} chunks</span></div></label>;
      })}{!filteredDocuments.length ? <div className="zkd-source-empty">No sources found.</div> : null}</div>
    </aside>
  </div>;
}

function Composer({ query, modelId, pending, selectionRequired, variant, onChange, onSubmit }: { query: string; modelId: string; pending: boolean; selectionRequired: boolean; variant: "hero" | "conversation"; onChange: (value: string) => void; onSubmit: () => void }) {
  const disabled = !query.trim() || pending || selectionRequired;
  return <div className={`zkd-composer zkd-composer--${variant}`}><textarea aria-label="Question" rows={variant === "hero" ? 3 : 2} value={query} placeholder="Type a command..." onChange={(event) => onChange(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); if (!disabled) onSubmit(); } }} /><div className="zkd-composer-footer"><div className="zkd-model"><span className="zkd-model-dot" /><span>{modelId}</span></div><div className="zkd-composer-actions">{selectionRequired ? <span className="zkd-scope-warning">Select a source</span> : null}<button className="zkd-send" type="button" aria-label="Send message" disabled={disabled} onClick={onSubmit}><ArrowUp size={17} strokeWidth={2.1} /></button></div></div></div>;
}

function LocalAnswer({ message, onCitation, onRetry }: { message: LocalAssistantMessage; onCitation: (citation: Citation) => void; onRetry: () => void }) {
  const result = message.result;
  return <article className="zkd-message zkd-message--assistant" aria-live={message.state === "PENDING" ? "polite" : undefined}><div className="zkd-assistant-heading"><ZkdWordmark /></div>{message.state === "PENDING" ? <div className="zkd-thinking">Thinking…</div> : null}{message.state === "FAILED" ? <div className="zkd-answer-failure"><ErrorNotice error={message.error} /><button type="button" onClick={onRetry}>Retry</button></div> : null}{result?.answer_text ? <div className="zkd-answer-content"><CitedAnswer text={result.answer_text} citations={message.citations} onCitation={onCitation} /></div> : null}{result?.status === "INSUFFICIENT_EVIDENCE" ? <div className="zkd-answer-note">The selected sources do not contain enough evidence for this answer.</div> : null}</article>;
}
