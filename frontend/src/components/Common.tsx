import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { Candidate, ChunkDetail, Citation, SelectedEvidence } from "../types";

export function StatusBadge({ value }: { value: string }) {
  const tone = /PASS|COMPLETED|ANSWERABLE|AVAILABLE|RETAINED|FOUND|STRICT_MATCH/i.test(value)
    ? "good"
    : /FAIL|ERROR|INVALID|UNSUPPORTED|MISS|DROP/i.test(value)
      ? "bad"
      : /WARNING|INSUFFICIENT|FALSE_ABSTENTION|FALLBACK|PENDING|PROCESSING/i.test(value)
        ? "warn"
        : "neutral";
  return <span className={`badge ${tone}`}>{value.replaceAll("_", " ")}</span>;
}

export function ErrorNotice({ error }: { error: unknown }) {
  if (!error) return null;
  const apiError = error instanceof ApiError ? error : null;
  return (
    <div className="notice error" role="alert">
      <strong>Request failed</strong>
      <span>{error instanceof Error ? error.message : String(error)}</span>
      {apiError?.requestId && <code>request_id: {apiError.requestId}</code>}
    </div>
  );
}

export function EmptyState({ children }: { children: React.ReactNode }) {
  return <div className="empty-state">{children}</div>;
}

export function JsonBlock({ value }: { value: unknown }) {
  return <pre className="json-block">{JSON.stringify(value, null, 2)}</pre>;
}

export function CandidateTable({ kind, candidates, onInspect }: {
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
          {kind !== "lexical" && <th>Dense</th>}
          {kind !== "dense" && <th>Lexical</th>}
          {kind === "rrf" && <th>Fusion</th>}
          <th>Content preview</th>
        </tr></thead>
        <tbody>{candidates.map((item) => (
          <tr key={`${kind}-${item.chunk_id}`}>
            <td>{kind === "dense" ? item.dense_rank : kind === "lexical" ? item.lexical_rank : kind === "context" || kind === "hierarchy" ? item.context_candidate_order : item.retrieval_final_rank ?? item.final_rank}</td>
            <td><button className="link-button mono" onClick={() => onInspect(item.chunk_id)}>{item.chunk_id.slice(0, 8)}</button></td>
            <td className="mono">{item.document_id.slice(0, 8)}</td>
            {kind !== "lexical" && <td>{formatSignal(item.dense_score)} <small>#{item.dense_rank ?? "—"}</small></td>}
            {kind !== "dense" && <td>{formatSignal(item.lexical_score)} <small>#{item.lexical_rank ?? "—"}</small></td>}
            {kind === "rrf" && <td>{formatSignal(item.fusion_score, 6)}</td>}
            <td className="preview">{item.content_preview || "No preview available"}</td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}

export function formatSignal(value?: number | null, digits = 4) {
  return value == null ? "—" : value.toFixed(digits);
}

export function SourceDrawer({ source, onClose }: {
  source: { chunkId: string; sourceId?: string } | null;
  onClose: () => void;
}) {
  const [detail, setDetail] = useState<ChunkDetail | null>(null);
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    if (!source) return;
    setDetail(null); setError(null);
    api.chunk(source.chunkId).then(setDetail).catch(setError);
  }, [source]);
  if (!source) return null;
  return (
    <div className="drawer-backdrop" onMouseDown={onClose}>
      <aside className="drawer" role="dialog" aria-modal="true" aria-label="Source evidence" onMouseDown={(event) => event.stopPropagation()}>
        <div className="drawer-head">
          <div><span className="eyebrow">Source inspector</span><h2>{source.sourceId ?? "Chunk detail"}</h2></div>
          <button aria-label="Close source drawer" onClick={onClose}>Close</button>
        </div>
        <ErrorNotice error={error} />
        {!detail && !error && <div className="loading">Loading stored provenance…</div>}
        {detail && <>
          <dl className="key-values">
            <dt>Chunk</dt><dd className="mono">{detail.chunk_id}</dd>
            <dt>Document</dt><dd className="mono">{detail.document_id}</dd>
            <dt>Legal unit</dt><dd className="mono">{detail.legal_unit_id ?? "—"}</dd>
            <dt>Pages</dt><dd>{detail.page_start}–{detail.page_end}</dd>
          </dl>
          <h3>Full evidence text</h3><div className="evidence-text">{detail.content_text}</div>
          <details><summary>Metadata</summary><JsonBlock value={detail.metadata_json} /></details>
          <details><summary>Stored provenance</summary><JsonBlock value={detail.provenance_json} /></details>
          <details><summary>Embedding text</summary><div className="evidence-text">{detail.embedding_text}</div></details>
        </>}
      </aside>
    </div>
  );
}

export function CitedAnswer({ text, citations, onCitation }: {
  text: string;
  citations: Citation[];
  onCitation: (citation: Citation) => void;
}) {
  const citationMap = new Map(citations.map((item) => [item.source_id, item]));
  const parts = text.split(/(\[S[1-9][0-9]*\])/g);
  return <div className="answer-text">{parts.map((part, index) => {
    const sourceId = /^\[(S[1-9][0-9]*)\]$/.exec(part)?.[1];
    const citation = sourceId ? citationMap.get(sourceId) : undefined;
    return citation
      ? <button key={index} className="citation-link" onClick={() => onCitation(citation)}>{part}</button>
      : <span key={index}>{part}</span>;
  })}</div>;
}

export function EvidenceCards({ evidence, onInspect }: {
  evidence: SelectedEvidence[];
  onInspect: (chunkId: string, sourceId?: string) => void;
}) {
  if (!evidence.length) return <EmptyState>No evidence entered Block 5.</EmptyState>;
  return <div className="evidence-grid">{evidence.map((item) => (
    <article className="evidence-card" key={item.source_id}>
      <header><button className="source-token" onClick={() => onInspect(item.chunk_id, item.source_id)}>{item.source_id}</button><span>{item.token_count} tokens</span></header>
      <div className="rank-line">{item.candidate_origin === "HIERARCHY_CHILD" ? `Hierarchy ${item.hierarchy_relation} · anchor RRF #${item.anchor_retrieval_final_rank ?? "—"}` : `RRF #${item.retrieval_final_rank ?? "—"}`} · context #{item.context_candidate_order} · dense #{item.dense_rank ?? "—"} · lexical #{item.lexical_rank ?? "—"}</div>
      <p>{item.content_text}</p>
      <details><summary>Metadata & provenance</summary><JsonBlock value={{ metadata: item.metadata_json, provenance: item.provenance_json }} /></details>
    </article>
  ))}</div>;
}
