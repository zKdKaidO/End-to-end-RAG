import { useEffect, useState } from "react";
import { api } from "../api/client";
import { CandidateTable, CitedAnswer, EmptyState, ErrorNotice, EvidenceCards, JsonBlock, Metric, PageHeading, SourceDrawer, StatusBadge } from "../components/Common";
import type { Citation, DebugTrace, DocumentPipeline, EvaluationCase } from "../types";

export function DebugPage() {
  const [query, setQuery] = useState("");
  const [documentId, setDocumentId] = useState("");
  const [caseId, setCaseId] = useState("");
  const [documents, setDocuments] = useState<DocumentPipeline[]>([]);
  const [cases, setCases] = useState<EvaluationCase[]>([]);
  const [trace, setTrace] = useState<DebugTrace | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [source, setSource] = useState<{ chunkId: string; sourceId?: string } | null>(null);
  useEffect(() => { Promise.all([api.documents(), api.evaluationCases()]).then(([docs, values]) => { setDocuments(docs); setCases(values); }).catch(setError); }, []);
  const selectCase = (id: string) => {
    setCaseId(id);
    const selected = cases.find((item) => item.case_id === id);
    if (selected) { setQuery(selected.question); setDocumentId(""); }
  };
  const run = async () => {
    setLoading(true); setError(null); setTrace(null);
    try { setTrace(await api.debug({ query_text: query, document_ids: documentId ? [documentId] : null, evaluation_case_id: caseId || null })); }
    catch (value) { setError(value); }
    finally { setLoading(false); }
  };
  const inspect = (chunkId: string, sourceId?: string) => setSource({ chunkId, sourceId });
  const cite = (citation: Citation) => inspect(citation.chunk_id, citation.source_id);
  if (typeof error === "object" && error !== null && "status" in error && error.status === 404) return <div className="page"><PageHeading eyebrow="Internal tooling" title="Pipeline Debug" description="This route is intentionally available only in local or development environments." /><EmptyState>Internal diagnostics are disabled by the backend environment contract.</EmptyState></div>;
  return <div className="page">
    <PageHeading eyebrow="Blocks 4 → 5 → 6" title="Pipeline Debug" description="Run one real request and inspect retrieval, context selection, generation, and optional ground truth." />
    <section className="panel debug-controls">
      <label>Evaluation case (optional)<select value={caseId} onChange={(event) => selectCase(event.target.value)}><option value="">Ad-hoc query — no correctness label</option>{cases.map((item) => <option key={item.case_id} value={item.case_id}>{item.case_id} · {item.category}</option>)}</select></label>
      <label>Question<textarea value={query} onChange={(event) => { setQuery(event.target.value); if (caseId && event.target.value !== cases.find((item) => item.case_id === caseId)?.question) setCaseId(""); }} rows={3} /></label>
      <label>Document filter<select disabled={!!caseId} value={documentId} onChange={(event) => setDocumentId(event.target.value)}><option value="">Production default</option>{documents.filter((item) => item.index_count).map((item) => <option value={item.document_id} key={item.document_id}>{item.filename}</option>)}</select></label>
      <button className="primary" onClick={run} disabled={!query.trim() || loading}>{loading ? "Running real pipeline…" : "Run Debug"}</button>
    </section>
    <ErrorNotice error={error} />
    {loading && <div className="loading large">Embedding, retrieving, selecting context, and generating with the real provider…</div>}
    {!trace && !loading && <EmptyState>No trace yet. Ad-hoc runs report observations only; evaluation cases add deterministic expected-vs-actual diagnosis.</EmptyState>}
    {trace && <div className="pipeline">
      <div className="trace-header"><div><span className="eyebrow">Request trace</span><h2>{trace.query_text}</h2></div><code>{trace.request_id}</code></div>
      <ol className="pipeline-rail" aria-label="RAG pipeline stages">
        {["Query", "Dense", "Lexical", "RRF", "Hierarchy", "Context build", "Generate"].map((label) => <li key={label}><span aria-hidden="true" />{label}</li>)}
      </ol>
      <Stage number="4" title="Retrieval" subtitle="Dense, lexical, and Python RRF">
        <div className="metric-grid"><Metric label="Dense" value={trace.retrieval.dense_candidate_count} /><Metric label="Lexical" value={trace.retrieval.lexical_candidate_count} /><Metric label="Overlap" value={trace.retrieval.overlap_count} /><Metric label="Lexical mode" value={<StatusBadge value={trace.retrieval.lexical_mode} />} /></div>
        <div className="signal-note">Scores are diagnostic ranking signals, not calibrated confidence.</div>
        <details><summary>Dense candidates</summary><CandidateTable kind="dense" candidates={trace.retrieval.dense_candidates} onInspect={inspect} /></details>
        <details><summary>Lexical candidates</summary><CandidateTable kind="lexical" candidates={trace.retrieval.lexical_candidates} onInspect={inspect} /></details>
        <details open><summary>Immutable RRF Top 10</summary><CandidateTable kind="rrf" candidates={trace.retrieval.rrf_candidates ?? trace.retrieval.final_candidates} onInspect={inspect} /></details>
        <details><summary>Hierarchy expansion ({trace.retrieval.hierarchy_candidates?.length ?? 0} added)</summary>
          <div className="signal-note">Direct children only. Server-owned bounds; no hierarchy tuning controls.</div>
          <CandidateTable kind="hierarchy" candidates={trace.retrieval.hierarchy_candidates ?? []} onInspect={inspect} />
          <JsonBlock value={trace.retrieval.hierarchy ?? { status: "NOT_CAPTURED" }} />
        </details>
        <details open><summary>Final context candidate order</summary><CandidateTable kind="context" candidates={trace.retrieval.final_context_candidates ?? trace.retrieval.final_candidates} onInspect={inspect} /></details>
      </Stage>
      <Stage number="5" title="Context" subtitle="Frozen deduplication and Greedy Stop">
        <div className="metric-grid"><Metric label="Candidates" value={trace.context.candidate_count} /><Metric label="Duplicates" value={trace.context.duplicate_count} /><Metric label="Selected" value={trace.context.selected_count} /><Metric label="Dropped" value={trace.context.dropped_count} /></div>
        <div className="budget-label"><span>Context budget</span><strong>{trace.context.context_token_count} / {trace.context.context_budget_tokens} tokens</strong></div>
        <div className="budget-track"><div style={{ width: `${Math.min(trace.context.budget_utilization_percent, 100)}%` }} /></div>
        <div className="result-meta"><span>{trace.context.budget_utilization_percent}% used</span><StatusBadge value={trace.context.stop_reason} /><span>Exhausted: {String(trace.context.budget_exhausted)}</span></div>
        <EvidenceCards evidence={trace.context.selected_evidence} onInspect={inspect} />
      </Stage>
      <Stage number="6" title="Generation" subtitle="Answerability, citations, and provenance">
        <div className="metric-grid"><Metric label="Public status" value={<StatusBadge value={trace.generation.status} />} /><Metric label="Answerability" value={<StatusBadge value={trace.generation.answerability_status ?? trace.generation.answerability_validation} />} /><Metric label="Citation validation" value={<StatusBadge value={trace.generation.citation_validation} />} /><Metric label="Prompt" value={trace.generation.prompt_version} /></div>
        <CitedAnswer text={trace.generation.answer_text} citations={trace.generation.citations} onCitation={cite} />
        {!trace.generation.citations.length && <EmptyState>No valid citations in this result.</EmptyState>}
        <div className="citation-row">{trace.generation.citations.map((item) => <button key={item.source_id} onClick={() => cite(item)}>{item.source_id} · RRF #{item.retrieval_final_rank ?? "—"}</button>)}</div>
        <details><summary>Provider-safe metadata</summary><JsonBlock value={{ model_id: trace.generation.model_id, prompt_version: trace.generation.prompt_version, prompt_tokens: trace.generation.prompt_token_count, context_tokens: trace.generation.context_token_count, finish_reason: trace.generation.finish_reason, usage: trace.generation.usage, generation_ms: trace.generation.generation_ms, ttft_ms: trace.generation.time_to_first_token_ms }} /></details>
      </Stage>
      <Stage number="✓" title="Expected vs actual" subtitle={trace.expected ? "Deterministic evaluation semantics" : "No ground truth supplied"}>
        {!trace.expected && <div className="notice neutral"><StatusBadge value="NO_GROUND_TRUTH" /> Ad-hoc traces do not claim that an answer is correct or incorrect.</div>}
        {trace.expected && <div className="comparison-grid"><section><span className="eyebrow">Expected</span><h3>{trace.expected.case_id}</h3><p>Answerable: <strong>{String(trace.expected.answerable)}</strong></p><p>{trace.expected.source_reference}</p><JsonBlock value={{ documents: trace.expected.expected_document_ids, acceptable_evidence_sets: trace.expected.acceptable_evidence_sets }} /></section><section><span className="eyebrow">Actual</span><h3><StatusBadge value={trace.diagnosis ?? "AMBIGUOUS"} /></h3><p>Retrieved: {trace.retrieval.final_candidates.map((item) => item.chunk_id.slice(0, 8)).join(", ")}</p><p>Selected: {trace.context.selected_evidence.map((item) => item.source_id).join(", ") || "none"}</p><p>Cited: {trace.generation.citations.map((item) => item.source_id).join(", ") || "none"}</p></section></div>}
      </Stage>
    </div>}
    <SourceDrawer source={source} onClose={() => setSource(null)} />
  </div>;
}

function Stage({ number, title, subtitle, children }: { number: string; title: string; subtitle: string; children: React.ReactNode }) {
  return <section className="stage"><header><span className="stage-number">{number}</span><div><span className="eyebrow">Block {number}</span><h2>{title}</h2><p>{subtitle}</p></div></header><div className="stage-body">{children}</div></section>;
}
