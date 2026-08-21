import { useEffect, useRef, useState } from "react";
import { streamAnswer } from "../api/client";
import { api } from "../api/client";
import { CitedAnswer, EmptyState, ErrorNotice, SourceDrawer, StatusBadge } from "../components/Common";
import type { Citation, DocumentPipeline, GenerationResult } from "../types";
import { PageHeading } from "./DocumentsPage";

export function AskPage() {
  const [query, setQuery] = useState("");
  const [documents, setDocuments] = useState<DocumentPipeline[]>([]);
  const [documentId, setDocumentId] = useState("");
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState<GenerationResult | null>(null);
  const [phase, setPhase] = useState("idle");
  const [error, setError] = useState<unknown>(null);
  const [source, setSource] = useState<{ chunkId: string; sourceId?: string } | null>(null);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => { api.documents().then(setDocuments).catch(() => undefined); }, []);
  const run = async () => {
    if (!query.trim()) return;
    controller.current = new AbortController();
    setAnswer(""); setResult(null); setError(null); setPhase("connecting");
    try {
      await streamAnswer(
        { query_text: query, document_ids: documentId ? [documentId] : null },
        {
          start: () => setPhase("streaming"),
          delta: (text) => setAnswer((current) => current + text),
          done: (value) => { setResult(value); setAnswer(value.answer_text); setPhase("done"); },
          error: (value) => { setError(new Error(String(value.safe_message ?? "Provider stream failed"))); setPhase("error"); },
        },
        controller.current.signal,
      );
    } catch (value) {
      if ((value as Error).name === "AbortError") setPhase("cancelled");
      else { setError(value); setPhase("error"); }
    }
  };
  const inspect = (citation: Citation) => setSource({ chunkId: citation.chunk_id, sourceId: citation.source_id });
  return <div className="page narrow-page">
    <PageHeading eyebrow="Block 6 streaming" title="Ask" description="Stream a grounded answer through the frozen production endpoint." />
    <section className="panel query-panel">
      <label>Question<textarea value={query} onChange={(event) => setQuery(event.target.value)} rows={4} placeholder="Ask a Vietnamese legal question…" /></label>
      <label>Document filter<select value={documentId} onChange={(event) => setDocumentId(event.target.value)}><option value="">All indexed documents</option>{documents.filter((item) => item.index_count).map((item) => <option key={item.document_id} value={item.document_id}>{item.filename}</option>)}</select></label>
      <div className="actions"><button className="primary" onClick={run} disabled={!query.trim() || ["connecting", "streaming"].includes(phase)}>Ask</button>{["connecting", "streaming"].includes(phase) && <button onClick={() => controller.current?.abort()}>Stop generation</button>}<StatusBadge value={phase} /></div>
    </section>
    <ErrorNotice error={error} />
    <section className="panel answer-panel">
      <div className="section-title"><div><span className="eyebrow">Answer</span><h2>{result ? <StatusBadge value={result.status} /> : "Waiting for a query"}</h2></div>{result && <code>{result.request_id}</code>}</div>
      {!answer && phase === "idle" && <EmptyState>Submit a question to stream an answer.</EmptyState>}
      {!answer && phase === "streaming" && <div className="loading">The provider is preparing the first token…</div>}
      {answer && <CitedAnswer text={answer} citations={result?.citations ?? []} onCitation={inspect} />}
      {result && <div className="result-meta"><StatusBadge value={result.answerability_status ?? result.answerability_validation} /><span>Citations: {result.citations.length}</span><span>Validation: {result.citation_validation}</span><span>{result.model_id}</span></div>}
      {result?.status === "COMPLETED_WITH_WARNINGS" && <div className="notice warning">The answer completed with citation or output-contract warnings.</div>}
      {result?.status === "INSUFFICIENT_EVIDENCE" && <div className="notice warning">The selected evidence does not support the exact requested fact.</div>}
      {result && !result.citations.length && result.status !== "INSUFFICIENT_EVIDENCE" && <EmptyState>No valid citations were mapped.</EmptyState>}
      {!!result?.citations.length && <div className="citation-row">{result.citations.map((item) => <button key={item.source_id} onClick={() => inspect(item)}>{item.source_id} · page {String(item.provenance_json.page_start ?? "—")}</button>)}</div>}
    </section>
    <SourceDrawer source={source} onClose={() => setSource(null)} />
  </div>;
}
