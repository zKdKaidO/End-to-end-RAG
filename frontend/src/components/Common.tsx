import { memo, useEffect, useId, useRef, useState } from "react";
import { ChevronRight, ExternalLink, FileText, X } from "lucide-react";
import { api } from "../api/client";
import type { Candidate, ChunkDetail, Citation, SelectedEvidence } from "../types";

export function PageHeading({ eyebrow, title, description, actions }: {
  eyebrow: string;
  title: string;
  description: string;
  actions?: React.ReactNode;
}) {
  return (
    <header className="page-heading">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </header>
  );
}

export function Metric({ label, value, detail }: {
  label: string;
  value: React.ReactNode;
  detail?: React.ReactNode;
}) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value ?? "—"}</strong>
      {detail ? <small>{detail}</small> : null}
    </div>
  );
}

export function StatusBadge({ value }: { value: string }) {
  const tone = /PASS|COMPLETED|ANSWERABLE|AVAILABLE|RETAINED|FOUND|STRICT_MATCH|READY/i.test(value)
    ? "good"
    : /FAIL|ERROR|INVALID|UNSUPPORTED|MISS|DROP|UNAVAILABLE/i.test(value)
      ? "bad"
      : /WARNING|INSUFFICIENT|FALSE_ABSTENTION|FALLBACK|PENDING|PROCESSING|CONNECTING|STREAMING/i.test(value)
        ? "warn"
        : "neutral";
  return <span className={`badge ${tone}`}>{value.replaceAll("_", " ")}</span>;
}

export function ErrorNotice({ error, title = "Request failed" }: { error: unknown; title?: string }) {
  if (!error) return null;
  const requestId = typeof error === "object" && error !== null && "requestId" in error ? String(error.requestId ?? "") : "";
  return (
    <div className="notice error" role="alert">
      <strong>{title}</strong>
      <span>{error instanceof Error ? error.message : String(error)}</span>
      {requestId ? <code>request_id: {requestId}</code> : null}
    </div>
  );
}

export function EmptyState({ children, icon = <FileText size={18} /> }: {
  children: React.ReactNode;
  icon?: React.ReactNode;
}) {
  return <div className="empty-state">{icon}<span>{children}</span></div>;
}

export function JsonBlock({ value }: { value: unknown }) {
  return <pre className="json-block">{JSON.stringify(value, null, 2)}</pre>;
}

export function Drawer({ open, title, eyebrow, wide = false, onClose, children }: {
  open: boolean;
  title: string;
  eyebrow: string;
  wide?: boolean;
  onClose: () => void;
  children: React.ReactNode;
}) {
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    previousFocus.current = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key === "Tab") {
        const panel = closeRef.current?.closest<HTMLElement>("[role='dialog']");
        const focusable = Array.from(panel?.querySelectorAll<HTMLElement>("button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), summary, [tabindex]:not([tabindex='-1'])") ?? []);
        if (!focusable.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      previousFocus.current?.focus();
    };
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="drawer-backdrop" onMouseDown={onClose}>
      <aside
        className={`drawer ${wide ? "wide" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="drawer-head">
          <div>
            <span className="eyebrow">{eyebrow}</span>
            <h2 id={titleId}>{title}</h2>
          </div>
          <button ref={closeRef} className="icon-button" aria-label="Close panel" onClick={onClose}>
            <X size={17} />
          </button>
        </div>
        {children}
      </aside>
    </div>
  );
}

export const CandidateTable = memo(function CandidateTable({ kind, candidates, onInspect }: {
  kind: "dense" | "lexical" | "rrf" | "hierarchy" | "context";
  candidates: Candidate[];
  onInspect: (chunkId: string, sourceId?: string) => void;
}) {
  if (!candidates.length) return <EmptyState>No {kind} candidates.</EmptyState>;
  return (
    <div className="table-scroll">
      <table>
        <thead><tr>
          <th>Rank</th><th>Chunk</th><th>Document</th>
          {kind !== "lexical" ? <th>Dense</th> : null}
          {kind !== "dense" ? <th>Lexical</th> : null}
          {kind === "rrf" ? <th>Fusion</th> : null}
          <th>Evidence preview</th>
        </tr></thead>
        <tbody>{candidates.map((item) => (
          <tr key={`${kind}-${item.chunk_id}`}>
            <td>{kind === "dense" ? item.dense_rank : kind === "lexical" ? item.lexical_rank : kind === "context" || kind === "hierarchy" ? item.context_candidate_order : item.retrieval_final_rank ?? item.final_rank}</td>
            <td><button className="link-button mono" onClick={() => onInspect(item.chunk_id)}>{item.chunk_id.slice(0, 8)}</button></td>
            <td className="mono">{item.document_id.slice(0, 8)}</td>
            {kind !== "lexical" ? <td>{formatSignal(item.dense_score)} <small>#{item.dense_rank ?? "—"}</small></td> : null}
            {kind !== "dense" ? <td>{formatSignal(item.lexical_score)} <small>#{item.lexical_rank ?? "—"}</small></td> : null}
            {kind === "rrf" ? <td>{formatSignal(item.fusion_score, 6)}</td> : null}
            <td className="preview">{item.content_preview || "No preview available"}</td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
});

export function formatSignal(value?: number | null, digits = 4) {
  return value == null ? "—" : value.toFixed(digits);
}

export function SourceDrawer({ source, citation, onClose }: {
  source: { chunkId: string; sourceId?: string } | null;
  citation?: Citation | null;
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<ChunkDetail | null>(null);
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    if (!source) return;
    let active = true;
    setDetail(null);
    setError(null);
    if (citation?.evidence_text != null) return () => { active = false; };
    api.chunk(source.chunkId)
      .then((value) => active && setDetail(value))
      .catch((value) => active && setError(value));
    return () => { active = false; };
  }, [citation?.evidence_text, source]);
  return (
    <Drawer open={Boolean(source)} title={source?.sourceId ?? "Chunk detail"} eyebrow="Source inspector" onClose={onClose}>
      {citation ? <CitationSummary citation={citation} /> : null}
      {citation?.availability === "SOURCE_UPDATED" ? <div className="notice warning">The current source differs from the version used when this answer was generated.</div> : null}
      {citation?.availability === "SOURCE_UNAVAILABLE" ? <div className="notice neutral">The original source is no longer available in the current library. This is the evidence snapshot stored when the answer was generated.</div> : null}
      {citation?.availability === "CURRENT_EQUIVALENT" ? <div className="notice neutral">Current equivalent source available. The historical snapshot remains authoritative for this answer.</div> : null}
      {citation?.evidence_text != null ? <>
        <h3>Historical evidence snapshot</h3>
        <div className="evidence-text">{citation.evidence_text}</div>
        <details><summary>Snapshot metadata</summary><JsonBlock value={citation.metadata_json} /></details>
        <details><summary>Snapshot provenance</summary><JsonBlock value={citation.provenance_json} /></details>
      </> : null}
      {error ? (
        <div className="notice neutral">
          <span>Full source text is available only when internal diagnostics are enabled. Citation metadata remains authoritative.</span>
        </div>
      ) : null}
      {!citation?.evidence_text && !detail && !error ? <div className="loading">Loading stored provenance…</div> : null}
      {detail ? <>
        <dl className="key-values">
          <dt>Chunk</dt><dd className="mono">{detail.chunk_id}</dd>
          <dt>Document</dt><dd className="mono">{detail.document_id}</dd>
          <dt>Legal unit</dt><dd className="mono">{detail.legal_unit_id ?? "—"}</dd>
          <dt>Pages</dt><dd>{detail.page_start}–{detail.page_end}</dd>
        </dl>
        <h3>Full evidence text</h3>
        <div className="evidence-text">{detail.content_text}</div>
        <details><summary>Metadata</summary><JsonBlock value={detail.metadata_json} /></details>
        <details><summary>Stored provenance</summary><JsonBlock value={detail.provenance_json} /></details>
        <details><summary>Embedding text</summary><div className="evidence-text">{detail.embedding_text}</div></details>
      </> : null}
    </Drawer>
  );
}

export function CitationSummary({ citation }: { citation: Citation }) {
  const page = citation.page_start ?? citation.provenance_json.page_start ?? citation.page_end ?? citation.provenance_json.page_end;
  return (
    <dl className="key-values citation-summary">
      <dt>Source</dt><dd><strong>{citation.source_id}</strong></dd>
      <dt>Chunk</dt><dd className="mono">{citation.chunk_id || "Historical ID unavailable"}</dd>
      <dt>Document</dt><dd className="mono">{citation.document_filename ?? citation.document_title ?? citation.document_id ?? "Historical ID unavailable"}</dd>
      <dt>Page</dt><dd>{page == null ? "—" : String(page)}</dd>
      <dt>Rank</dt><dd>{citation.retrieval_final_rank ?? "—"}</dd>
    </dl>
  );
}

export const CitedAnswer = memo(function CitedAnswer({ text, citations, onCitation }: {
  text: string;
  citations: Citation[];
  onCitation: (citation: Citation) => void;
}) {
  const citationMap = new Map(citations.map((item) => [item.source_id, item]));
  const parts = text.split(/(\[S[1-9][0-9]*\])/g);
  return <div className="answer-text">{parts.map((part, index) => {
    const sourceId = /^\[(S[1-9][0-9]*)\]$/.exec(part)?.[1];
    const citation = sourceId ? citationMap.get(sourceId) : undefined;
    return citation ? (
      <button
        key={`${part}-${index}`}
        className="citation-link"
        onClick={() => onCitation(citation)}
        aria-label={part}
        title={`Inspect source ${citation.source_id}`}
      >
        {part}
        <span className="citation-preview" role="tooltip">
          <strong>{citation.source_id}</strong>
          <span>{citation.document_filename ?? (citation.document_id ? `Document ${citation.document_id.slice(0, 8)}` : "Historical source")} · page {String(citation.page_start ?? citation.provenance_json.page_start ?? "—")}</span>
          <small>Open exact provenance</small>
        </span>
      </button>
    ) : <span key={`${part}-${index}`}>{part}</span>;
  })}</div>;
});

export function SourceList({ citations, activeSourceId, onInspect }: {
  citations: Citation[];
  activeSourceId?: string | null;
  onInspect: (citation: Citation) => void;
}) {
  if (!citations.length) return <EmptyState>No valid sources were mapped for this answer.</EmptyState>;
  return (
    <div className="source-list">
      {citations.map((citation) => (
        <button
          key={citation.source_id}
          id={`source-${citation.source_id}`}
          className={`source-row ${activeSourceId === citation.source_id ? "active" : ""}`}
          onClick={() => onInspect(citation)}
        >
          <span className="source-index">{citation.source_id}</span>
          <span className="source-copy">
            <strong>{citation.document_filename ?? (citation.document_id ? `Document ${citation.document_id.slice(0, 8)}` : "Historical source")}</strong>
            <small>Page {String(citation.page_start ?? citation.provenance_json.page_start ?? "—")} · {citation.availability?.replaceAll("_", " ") ?? `RRF #${citation.retrieval_final_rank ?? "—"}`}</small>
          </span>
          <ChevronRight size={15} />
        </button>
      ))}
    </div>
  );
}

export function EvidenceCards({ evidence, onInspect }: {
  evidence: SelectedEvidence[];
  onInspect: (chunkId: string, sourceId?: string) => void;
}) {
  if (!evidence.length) return <EmptyState>No evidence entered Block 5.</EmptyState>;
  return <div className="evidence-grid">{evidence.map((item) => (
    <article className="evidence-card" key={item.source_id}>
      <header>
        <button className="source-token" onClick={() => onInspect(item.chunk_id, item.source_id)}>
          {item.source_id}<ExternalLink size={12} />
        </button>
        <span>{item.token_count} tokens</span>
      </header>
      <div className="rank-line">{item.candidate_origin === "HIERARCHY_CHILD" ? `Hierarchy ${item.hierarchy_relation} · anchor RRF #${item.anchor_retrieval_final_rank ?? "—"}` : `RRF #${item.retrieval_final_rank ?? "—"}`} · context #{item.context_candidate_order} · dense #{item.dense_rank ?? "—"} · lexical #{item.lexical_rank ?? "—"}</div>
      <p>{item.content_text}</p>
      <details><summary>Metadata & provenance</summary><JsonBlock value={{ metadata: item.metadata_json, provenance: item.provenance_json }} /></details>
    </article>
  ))}</div>;
}
