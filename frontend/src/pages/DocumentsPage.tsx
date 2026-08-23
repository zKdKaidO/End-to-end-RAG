import { useEffect, useMemo, useState } from "react";
import { FileSearch, RefreshCw, Search, Upload } from "lucide-react";
import { api } from "../api/client";
import { Drawer, EmptyState, ErrorNotice, JsonBlock, Metric, PageHeading, StatusBadge } from "../components/Common";
import type { AuthUser, DocumentPipeline } from "../types";

export function DocumentsPage({ user }: { user?: AuthUser }) {
  const [documents, setDocuments] = useState<DocumentPipeline[]>([]);
  const [selected, setSelected] = useState<DocumentPipeline | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState("");
  const [search, setSearch] = useState("");
  const [visibleLimit, setVisibleLimit] = useState(100);
  const [uploadAccess, setUploadAccess] = useState<"private" | "global">("private");

  const load = () => {
    setLoading(true);
    setError(null);
    api.documents().then(setDocuments).catch(setError).finally(() => setLoading(false));
  };
  useEffect(load, []);

  const visible = useMemo(() => {
    const term = search.trim().toLocaleLowerCase("vi");
    return term ? documents.filter((item) => `${item.filename} ${item.document_id}`.toLocaleLowerCase("vi").includes(term)) : documents;
  }, [documents, search]);

  const upload = async (file?: File) => {
    if (!file) return;
    setUploading(true);
    setError(null);
    setUploadMessage(`Uploading ${file.name}…`);
    try {
      await api.upload(file, uploadAccess);
      setUploadMessage(`${file.name} accepted for synchronous ingestion.`);
      load();
    } catch (value) {
      setUploadMessage("");
      setError(value);
    } finally {
      setUploading(false);
    }
  };

  const open = async (document: DocumentPipeline) => {
    setSelected(document);
    try { setSelected(await api.document(document.document_id)); } catch (value) { setError(value); }
  };

  const indexed = documents.filter((item) => item.indexing.status.toUpperCase().includes("COMPLETED") || item.index_count > 0).length;
  const failed = documents.filter((item) => [item.ingestion, item.processing, item.indexing].some((stage) => /FAIL|ERROR/i.test(stage.status))).length;

  return (
    <div className="page documents-page">
      <PageHeading
        eyebrow="Corpus operations"
        title="Documents"
        description="Upload legal sources and inspect their immutable ingestion, processing, and indexing lineage."
        actions={<div className="upload-actions">{user?.role === "ADMIN" ? <label>Access<select aria-label="Upload access" value={uploadAccess} onChange={(event) => setUploadAccess(event.target.value as "private" | "global")}><option value="private">Private</option><option value="global">Global</option></select></label> : null}<label className="upload-button primary"><Upload size={15} />{uploading ? "Uploading…" : "Upload PDF"}<input type="file" accept="application/pdf" disabled={uploading} onChange={(event) => void upload(event.target.files?.[0])} /></label></div>}
      />
      <section className="document-summary" aria-label="Corpus summary">
        <Metric label="Documents" value={documents.length} />
        <Metric label="Indexed" value={indexed} />
        <Metric label="Pipeline failures" value={failed} />
        <Metric label="Stored chunks" value={documents.reduce((sum, item) => sum + item.chunk_count, 0)} />
      </section>
      <div className="list-toolbar">
        <label className="search-control"><Search size={15} /><span className="sr-only">Search documents</span><input aria-label="Search documents" value={search} onChange={(event) => { setSearch(event.target.value); setVisibleLimit(100); }} placeholder="Search filename or document ID" /></label>
        <span>{visible.length} of {documents.length}</span>
        <button className="compact-button" onClick={load} disabled={loading}><RefreshCw size={14} /> Refresh</button>
      </div>
      {uploadMessage ? <div className="notice neutral" role="status"><span>{uploadMessage}</span></div> : null}
      <ErrorNotice error={error} title="Document service unavailable" />
      {loading ? <div className="loading">Loading corpus pipeline state…</div> : null}
      {!loading && !visible.length ? <EmptyState icon={<FileSearch size={19} />}>{documents.length ? "No documents match this search." : "No documents are stored. Upload a PDF to start the frozen ingestion pipeline."}</EmptyState> : null}
      {visible.length ? <section className="document-list panel" aria-label="Stored documents">
        <div className="document-list-head"><span>Document</span><span>Pipeline</span><span>Corpus</span><span>Created</span></div>
        {visible.slice(0, visibleLimit).map((item) => <button className="document-row" key={item.document_id} onClick={() => void open(item)}>
          <span className="document-name"><strong>{item.filename}</strong><code>{item.document_id}</code>{item.access_origin ? <StatusBadge value={item.access_origin} /> : null}</span>
          <span className="pipeline-badges"><StatusBadge value={item.ingestion.status} /><StatusBadge value={item.processing.status} /><StatusBadge value={item.indexing.status} /></span>
          <span className="document-counts">{item.page_count} pages · {item.chunk_count} chunks</span>
          <span>{item.created_at ? new Date(item.created_at).toLocaleString() : "—"}</span>
        </button>)}
        {visible.length > visibleLimit ? <button className="show-more" onClick={() => setVisibleLimit((value) => value + 100)}>Show 100 more documents <span>{visibleLimit} of {visible.length} rendered</span></button> : null}
      </section> : null}
      <DocumentDetail document={selected} onClose={() => setSelected(null)} />
    </div>
  );
}

function DocumentDetail({ document, onClose }: { document: DocumentPipeline | null; onClose: () => void }) {
  return (
    <Drawer open={Boolean(document)} wide title={document?.filename ?? "Document"} eyebrow="Document lineage" onClose={onClose}>
      {document ? <>
        <div className="metric-grid compact"><Metric label="Pages" value={document.page_count} /><Metric label="Legal units" value={document.legal_unit_count} /><Metric label="Chunks" value={document.chunk_count} /><Metric label="Indexes" value={document.index_count} /></div>
        <dl className="key-values"><dt>Document ID</dt><dd className="mono">{document.document_id}</dd><dt>Access</dt><dd>{document.access_origin ?? "—"}</dd><dt>MIME type</dt><dd>{document.mime_type}</dd><dt>File size</dt><dd>{formatBytes(document.file_size)}</dd></dl>
        <div className="stage-grid">{(["ingestion", "processing", "indexing"] as const).map((stage) => <section className="panel stage-card" key={stage}><span className="eyebrow">{stage}</span><StatusBadge value={document[stage].status} /><p>{document[stage].current_stage ?? "No active stage"}</p>{document[stage].error_message ? <div className="notice error">{document[stage].error_stage}: {document[stage].error_message}</div> : null}</section>)}</div>
        <div className="section-title"><div><span className="eyebrow">Evidence units</span><h2>Stored chunks</h2></div><span>{document.chunks?.length ?? 0}</span></div>
        {!document.chunks?.length ? <EmptyState>No chunks are stored for this document.</EmptyState> : null}
        {document.chunks?.map((chunk) => <details key={chunk.chunk_id}><summary><code>{chunk.chunk_id.slice(0, 8)}</code> · pages {chunk.page_start}–{chunk.page_end}</summary><div className="evidence-text">{chunk.content_text}</div><JsonBlock value={{ metadata: chunk.metadata_json, provenance: chunk.provenance_json }} /></details>)}
      </> : null}
    </Drawer>
  );
}

function formatBytes(value: number) {
  if (!value) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const unit = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
  return `${(value / 1024 ** unit).toFixed(unit ? 1 : 0)} ${units[unit]}`;
}
