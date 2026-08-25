import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle, CheckCircle2, Database, Eye, FileSearch, FileText, RefreshCw, Search, Trash2, Upload } from "lucide-react";
import { api } from "../api/client";
import { Drawer, EmptyState, ErrorNotice, JsonBlock, Metric, StatusBadge } from "../components/Common";
import { DocumentDeleteDialog } from "../components/documents/DocumentDeleteDialog";
import { documentStatusClasses, getDocumentDisplayState, matchesDocumentFilter, type DocumentFilter } from "../components/documents/documentStatus";
import { ProductShell } from "../components/product/ProductShell";
import type { AuthUser, DocumentPipeline } from "../types";

const DEFAULT_USER: AuthUser = { id: "standalone", email: "user@local", role: "USER", status: "ACTIVE", must_change_password: false };

export function DocumentsPage({ user = DEFAULT_USER, onLogout = () => undefined }: { user?: AuthUser; onLogout?: () => void }) {
  const [documents, setDocuments] = useState<DocumentPipeline[]>([]);
  const [selected, setSelected] = useState<DocumentPipeline | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<DocumentPipeline | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState("");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<DocumentFilter>("ALL");
  const [visibleLimit, setVisibleLimit] = useState(50);
  const [uploadAccess, setUploadAccess] = useState<"private" | "global">("private");
  const [rowAction, setRowAction] = useState<Record<string, "index" | "delete">>({});
  const loadInFlight = useRef(false);

  const load = useCallback(async (quiet = false) => {
    if (loadInFlight.current) return;
    loadInFlight.current = true;
    if (!quiet) { setLoading(true); setError(null); }
    try { setDocuments(await api.documents()); }
    catch (value) { if (!quiet) setError(value); throw value; }
    finally { loadInFlight.current = false; if (!quiet) setLoading(false); }
  }, []);

  useEffect(() => { void load().catch(() => undefined); }, [load]);

  const hasActivePipeline = documents.some((item) => getDocumentDisplayState(item).active);
  useEffect(() => {
    if (!hasActivePipeline) return;
    let stopped = false, failures = 0;
    let timer: number | undefined;
    const schedule = (delay: number) => { timer = window.setTimeout(poll, delay); };
    const poll = async () => {
      if (stopped) return;
      if (window.document.visibilityState === "hidden") { schedule(4_000); return; }
      try { await load(true); failures = 0; } catch { failures += 1; }
      if (!stopped) schedule(Math.min(20_000, 4_000 * 2 ** Math.min(failures, 2)));
    };
    const visibility = () => { if (!stopped && window.document.visibilityState === "visible") { if (timer) window.clearTimeout(timer); schedule(0); } };
    window.document.addEventListener("visibilitychange", visibility);
    schedule(4_000);
    return () => { stopped = true; if (timer) window.clearTimeout(timer); window.document.removeEventListener("visibilitychange", visibility); };
  }, [hasActivePipeline, load]);

  const visible = useMemo(() => {
    const term = search.trim().toLocaleLowerCase("vi");
    return documents.filter((item) => (!term || `${item.filename} ${item.document_id}`.toLocaleLowerCase("vi").includes(term)) && matchesDocumentFilter(item, filter));
  }, [documents, filter, search]);

  const metrics = useMemo(() => ({
    total: documents.length,
    ready: documents.filter((item) => getDocumentDisplayState(item).key === "READY").length,
    failed: documents.filter((item) => getDocumentDisplayState(item).failed).length,
    chunks: documents.reduce((sum, item) => sum + item.chunk_count, 0),
  }), [documents]);

  const upload = async (file?: File) => {
    if (!file) return;
    setUploading(true); setError(null); setUploadMessage(`Uploading ${file.name}…`);
    try { await api.upload(file, uploadAccess); setUploadMessage(`${file.name} was accepted for ingestion.`); await load(true); }
    catch (value) { setUploadMessage(""); setError(value); }
    finally { setUploading(false); }
  };

  const open = async (document: DocumentPipeline) => {
    setSelected(document);
    try { setSelected(await api.document(document.document_id)); } catch (value) { setError(value); }
  };

  const index = async (document: DocumentPipeline) => {
    setRowAction((items) => ({ ...items, [document.document_id]: "index" })); setError(null);
    try { await api.indexDocument(document.document_id); await load(true); }
    catch (value) { setError(value); }
    finally { setRowAction((items) => { const next = { ...items }; delete next[document.document_id]; return next; }); }
  };

  const remove = async () => {
    if (!deleteTarget) return;
    const target = deleteTarget;
    setRowAction((items) => ({ ...items, [target.document_id]: "delete" })); setError(null);
    try { await api.deleteDocument(target.document_id); setDeleteTarget(null); setSelected((item) => item?.document_id === target.document_id ? null : item); await load(true); }
    catch (value) { setError(value); }
    finally { setRowAction((items) => { const next = { ...items }; delete next[target.document_id]; return next; }); }
  };

  return <ProductShell sidebar={{ user, onLogout }}><div className="h-full overflow-y-auto bg-slate-50">
    <div className="mx-auto max-w-[1320px] px-4 pb-10 pt-6 sm:px-7">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-3 pl-10 min-[900px]:pl-0"><div><h1 className="m-0 text-xl font-semibold text-slate-900">Documents</h1><p className="mb-0 mt-1 text-xs text-slate-500">Your accessible indexed legal corpus and pipeline state.</p></div><div className="flex items-center gap-2">{user.role === "ADMIN" ? <label className="text-xs text-slate-500">Access <select aria-label="Upload access" className="ml-1 border-slate-200 bg-white text-xs" value={uploadAccess} onChange={(event) => setUploadAccess(event.target.value as "private" | "global")}><option value="private">Private</option><option value="global">Global</option></select></label> : null}<label className="inline-flex cursor-pointer items-center gap-2 rounded-md bg-blue-600 px-3 py-2 text-xs font-semibold text-white shadow-sm"><Upload size={14}/>{uploading ? "Uploading…" : "Upload PDF"}<input className="sr-only" type="file" accept="application/pdf" disabled={uploading} onChange={(event) => void upload(event.target.files?.[0])}/></label></div></header>

      <section className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="Corpus summary">
        <SummaryCard label="Total documents" value={metrics.total} icon={<FileText size={17}/>} tone="blue" />
        <SummaryCard label="Indexed" value={metrics.ready} icon={<CheckCircle2 size={17}/>} tone="green" />
        <SummaryCard label="Pipeline failures" value={metrics.failed} icon={<AlertCircle size={17}/>} tone="red" />
        <SummaryCard label="Stored chunks" value={formatCount(metrics.chunks)} icon={<Database size={17}/>} tone="slate" />
      </section>

      <section className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm" aria-label="Document library">
        <div className="flex flex-wrap items-center gap-2 border-b border-slate-200 p-3">
          <label className="flex min-w-[220px] flex-1 items-center gap-2 rounded-md border border-slate-200 px-2"><Search size={14} className="text-slate-400"/><span className="sr-only">Search documents</span><input className="h-8 border-0 bg-transparent p-0 text-xs shadow-none outline-none" aria-label="Search documents" placeholder="Search documents…" value={search} onChange={(event) => { setSearch(event.target.value); setVisibleLimit(50); }}/></label>
          <label className="flex items-center gap-2 text-xs text-slate-500"><span className="sr-only">Filter</span><select aria-label="Filter documents" className="border-slate-200 bg-white text-xs" value={filter} onChange={(event) => { setFilter(event.target.value as DocumentFilter); setVisibleLimit(50); }}><option value="ALL">All statuses</option><option value="READY">Ready</option><option value="PROCESSING">Processing</option><option value="FAILED">Failed</option></select></label>
          <button className="gap-1 border-slate-200 bg-white px-3 py-2 text-xs text-slate-600" onClick={() => void load().catch(() => undefined)} disabled={loading} title="Refresh pipeline state"><RefreshCw size={13} className={loading ? "animate-spin" : ""}/> Refresh</button>
          <span className="text-[10px] text-slate-400">{visible.length} of {documents.length}</span>
        </div>
        {uploadMessage ? <div className="border-b border-blue-100 bg-blue-50 px-4 py-2 text-xs text-blue-700" role="status">{uploadMessage}</div> : null}
        {error ? <div className="p-3"><ErrorNotice error={error} title="Document action failed" /></div> : null}
        {loading && !documents.length ? <div className="loading">Loading document pipeline state…</div> : null}
        {!loading && !visible.length ? <div className="p-5"><EmptyState icon={<FileSearch size={19} />}>{documents.length ? "No documents match this search or filter." : "No documents are stored. Upload a PDF to start the frozen ingestion pipeline."}</EmptyState></div> : null}
        {visible.length ? <div className="overflow-x-auto"><table className="w-full min-w-[860px] border-collapse text-left text-xs"><thead><tr className="border-b border-slate-200 bg-slate-50 text-[9px] uppercase tracking-wider text-slate-500"><th className="px-4 py-3">Document</th><th className="px-3 py-3">Pages</th><th className="px-3 py-3">Date added</th><th className="px-3 py-3">Pipeline status</th><th className="px-3 py-3">Knowledge base</th><th className="px-3 py-3 text-right">Actions</th></tr></thead><tbody>{visible.slice(0, visibleLimit).map((document) => <DocumentRow key={document.document_id} document={document} action={rowAction[document.document_id]} onOpen={() => void open(document)} onIndex={() => void index(document)} onDelete={() => setDeleteTarget(document)} />)}</tbody></table></div> : null}
        {visible.length > visibleLimit ? <button className="m-3 w-[calc(100%-1.5rem)] border-slate-200 bg-white px-3 py-2 text-xs text-blue-700" onClick={() => setVisibleLimit((value) => value + 50)}>Load 50 more · {visibleLimit} of {visible.length} rendered</button> : null}
      </section>
    </div>
    <DocumentDetail document={selected} onClose={() => setSelected(null)} />
    <DocumentDeleteDialog document={deleteTarget} pending={deleteTarget ? rowAction[deleteTarget.document_id] === "delete" : false} onCancel={() => setDeleteTarget(null)} onConfirm={() => void remove()} />
  </div></ProductShell>;
}

function SummaryCard({ label, value, icon, tone }: { label: string; value: string | number; icon: React.ReactNode; tone: "blue" | "green" | "red" | "slate" }) {
  const color = { blue: "text-blue-600 bg-blue-50", green: "text-emerald-600 bg-emerald-50", red: "text-red-600 bg-red-50", slate: "text-slate-500 bg-slate-100" }[tone];
  return <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm"><div className="flex items-start justify-between"><div><span className="block text-[9px] font-semibold uppercase tracking-wider text-slate-500">{label}</span><strong className={`mt-2 block text-2xl font-semibold ${tone === "red" ? "text-red-600" : "text-slate-900"}`}>{value}</strong></div><span className={`grid h-8 w-8 place-items-center rounded-md ${color}`}>{icon}</span></div></div>;
}

function DocumentRow({ document, action, onOpen, onIndex, onDelete }: { document: DocumentPipeline; action?: "index" | "delete"; onOpen: () => void; onIndex: () => void; onDelete: () => void }) {
  const display = getDocumentDisplayState(document);
  const canDelete = Boolean(document.access_origin?.includes("PRIVATE"));
  return <tr className="border-b border-slate-100 last:border-0 hover:bg-slate-50"><td className="px-4 py-3"><button className="block max-w-[320px] border-0 bg-transparent p-0 text-left" onClick={onOpen} aria-label={`Open details for ${document.filename}`}><strong className="block truncate text-xs text-slate-800">{document.filename}</strong><small className="mt-1 block truncate font-mono text-[9px] text-slate-400">{document.document_id}</small></button></td><td className="px-3 py-3 text-slate-600">{document.page_count || "—"}</td><td className="whitespace-nowrap px-3 py-3 text-slate-600">{formatDate(document.created_at)}</td><td className="px-3 py-3"><span className={`inline-flex rounded-full px-2 py-1 text-[9px] font-semibold uppercase tracking-wide ring-1 ring-inset ${documentStatusClasses(display)}`}>{display.label}</span></td><td className="px-3 py-3"><span className="block text-slate-700">{document.chunk_count} chunks</span><small className="text-[9px] text-slate-400">{document.index_count} indexes · {document.access_origin ?? "Accessible"}</small></td><td className="px-3 py-3"><div className="flex justify-end gap-1"><button className="border-0 bg-transparent p-2 text-slate-400 hover:text-blue-600" aria-label={`Inspect ${document.filename}`} title="Inspect document" disabled={Boolean(action)} onClick={onOpen}><Eye size={14}/></button>{display.canIndex ? <button className="border-0 bg-transparent p-2 text-slate-400 hover:text-blue-600" aria-label={`${display.indexActionLabel} ${document.filename}`} title={display.indexActionLabel ?? undefined} disabled={Boolean(action)} onClick={onIndex}><RefreshCw size={14} className={action === "index" ? "animate-spin" : ""}/></button> : null}{canDelete ? <button className="border-0 bg-transparent p-2 text-slate-400 hover:text-red-600" aria-label={`Remove ${document.filename}`} title="Remove from private library" disabled={Boolean(action)} onClick={onDelete}><Trash2 size={14}/></button> : null}</div></td></tr>;
}

function DocumentDetail({ document, onClose }: { document: DocumentPipeline | null; onClose: () => void }) {
  return <Drawer open={Boolean(document)} wide title={document?.filename ?? "Document"} eyebrow="Document lineage" onClose={onClose}>{document ? <><div className="metric-grid compact"><Metric label="Pages" value={document.page_count} /><Metric label="Legal units" value={document.legal_unit_count} /><Metric label="Chunks" value={document.chunk_count} /><Metric label="Indexes" value={document.index_count} /></div><dl className="key-values"><dt>Document ID</dt><dd className="mono">{document.document_id}</dd><dt>Access</dt><dd>{document.access_origin ?? "—"}</dd><dt>MIME type</dt><dd>{document.mime_type}</dd><dt>File size</dt><dd>{formatBytes(document.file_size)}</dd></dl><div className="stage-grid">{(["ingestion", "processing", "indexing"] as const).map((stage) => <section className="panel stage-card" key={stage}><span className="eyebrow">{stage}</span><StatusBadge value={document[stage].status} /><p>{document[stage].current_stage ?? "No active stage"}</p>{document[stage].error_message ? <div className="notice error">{document[stage].error_stage}: {document[stage].error_message}</div> : null}</section>)}</div><div className="section-title"><div><span className="eyebrow">Evidence units</span><h2>Stored chunks</h2></div><span>{document.chunks?.length ?? 0}</span></div>{!document.chunks?.length ? <EmptyState>No chunks are stored for this document.</EmptyState> : null}{document.chunks?.map((chunk) => <details key={chunk.chunk_id}><summary><code>{chunk.chunk_id.slice(0, 8)}</code> · pages {chunk.page_start}–{chunk.page_end}</summary><div className="evidence-text">{chunk.content_text}</div><JsonBlock value={{ metadata: chunk.metadata_json, provenance: chunk.provenance_json }} /></details>)}</> : null}</Drawer>;
}

function formatDate(value?: string | null) { return value ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value)) : "—"; }
function formatCount(value: number) { return new Intl.NumberFormat().format(value); }
function formatBytes(value: number) { if (!value) return "0 B"; const units = ["B", "KB", "MB", "GB"]; const unit = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1); return `${(value / 1024 ** unit).toFixed(unit ? 1 : 0)} ${units[unit]}`; }
