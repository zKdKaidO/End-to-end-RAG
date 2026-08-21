import { useEffect, useState } from "react";
import { api } from "../api/client";
import { EmptyState, ErrorNotice, JsonBlock, StatusBadge } from "../components/Common";
import type { DocumentPipeline } from "../types";

export function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentPipeline[]>([]);
  const [selected, setSelected] = useState<DocumentPipeline | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const load = () => {
    setLoading(true); setError(null);
    api.documents().then(setDocuments).catch(setError).finally(() => setLoading(false));
  };
  useEffect(load, []);
  const upload = async (file?: File) => {
    if (!file) return;
    setUploading(true); setError(null);
    try { await api.upload(file); load(); } catch (value) { setError(value); }
    finally { setUploading(false); }
  };
  const open = async (document: DocumentPipeline) => {
    setSelected(document);
    try { setSelected(await api.document(document.document_id)); } catch (value) { setError(value); }
  };
  return <div className="page">
    <PageHeading eyebrow="Blocks 1–3" title="Documents" description="Inspect ingestion, legal processing, and indexing state from stored pipeline data." />
    <div className="toolbar">
      <label className="upload-button">{uploading ? "Uploading…" : "Upload PDF"}<input type="file" accept="application/pdf" disabled={uploading} onChange={(event) => upload(event.target.files?.[0])} /></label>
      <button onClick={load} disabled={loading}>Refresh</button>
      <span>{documents.length} documents</span>
    </div>
    <ErrorNotice error={error} />
    {loading && <div className="loading">Loading pipeline state…</div>}
    {!loading && !documents.length && <EmptyState>No documents are stored. Upload a PDF through the frozen ingestion endpoint.</EmptyState>}
    {!!documents.length && <div className="table-scroll panel"><table>
      <thead><tr><th>Filename</th><th>Document ID</th><th>Ingestion</th><th>Processing</th><th>Indexing</th><th>Pages</th><th>Chunks</th><th>Indexes</th><th>Created</th></tr></thead>
      <tbody>{documents.map((item) => <tr key={item.document_id}>
        <td><button className="link-button" onClick={() => open(item)}>{item.filename}</button></td>
        <td className="mono">{item.document_id.slice(0, 8)}</td>
        <td><StatusBadge value={item.ingestion.status} /></td><td><StatusBadge value={item.processing.status} /></td><td><StatusBadge value={item.indexing.status} /></td>
        <td>{item.page_count}</td><td>{item.chunk_count}</td><td>{item.index_count}</td><td>{item.created_at ? new Date(item.created_at).toLocaleString() : "—"}</td>
      </tr>)}</tbody>
    </table></div>}
    {selected && <div className="drawer-backdrop" onMouseDown={() => setSelected(null)}><aside className="drawer wide" role="dialog" aria-modal="true" aria-label="Document detail" onMouseDown={(event) => event.stopPropagation()}>
      <div className="drawer-head"><div><span className="eyebrow">Document detail</span><h2>{selected.filename}</h2></div><button onClick={() => setSelected(null)}>Close</button></div>
      <div className="metric-grid compact"><Metric label="Pages" value={selected.page_count} /><Metric label="Legal units" value={selected.legal_unit_count} /><Metric label="Chunks" value={selected.chunk_count} /><Metric label="Indexes" value={selected.index_count} /></div>
      <div className="stage-grid">{(["ingestion", "processing", "indexing"] as const).map((stage) => <section className="panel" key={stage}><span className="eyebrow">{stage}</span><h3><StatusBadge value={selected[stage].status} /></h3><p>{selected[stage].current_stage ?? "No active stage"}</p>{selected[stage].error_message && <div className="notice error">{selected[stage].error_stage}: {selected[stage].error_message}</div>}</section>)}</div>
      <h3>Stored chunks</h3>
      {!selected.chunks?.length && <EmptyState>No chunks are stored for this document.</EmptyState>}
      {selected.chunks?.map((chunk) => <details key={chunk.chunk_id}><summary><code>{chunk.chunk_id.slice(0, 8)}</code> · pages {chunk.page_start}–{chunk.page_end}</summary><div className="evidence-text">{chunk.content_text}</div><JsonBlock value={{ metadata: chunk.metadata_json, provenance: chunk.provenance_json }} /></details>)}
    </aside></div>}
  </div>;
}

export function PageHeading({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return <header className="page-heading"><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></header>;
}

export function Metric({ label, value }: { label: string; value: React.ReactNode }) {
  return <div className="metric-card"><span>{label}</span><strong>{value}</strong></div>;
}
