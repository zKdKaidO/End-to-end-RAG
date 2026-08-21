import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { EmptyState, ErrorNotice, JsonBlock, StatusBadge } from "../components/Common";
import type { DebugTrace, EvaluationAggregate, EvaluationCase, EvaluationComparison, EvaluationSummary } from "../types";
import { Metric, PageHeading } from "./DocumentsPage";

export function EvaluationPage() {
  const [datasetId, setDatasetId] = useState("legal_eval_v1");
  const [summary, setSummary] = useState<EvaluationSummary | null>(null);
  const [cases, setCases] = useState<EvaluationCase[]>([]);
  const [comparison, setComparison] = useState<EvaluationComparison | null>(null);
  const [filter, setFilter] = useState("ALL");
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [rerun, setRerun] = useState<DebugTrace | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    setSummary(null); setCases([]); setComparison(null); setDetail(null); setRerun(null); setError(null); setFilter("ALL");
    const comparison = datasetId === "legal_eval_v1" ? api.evaluationComparison() : Promise.resolve(null);
    Promise.all([api.evaluationSummary(datasetId), api.evaluationCases(datasetId), comparison])
      .then(([s, c, x]) => { setSummary(s); setCases(c); setComparison(x); })
      .catch(setError);
  }, [datasetId]);
  const diagnoses = useMemo(() => ["ALL", ...Array.from(new Set(cases.map((item) => item.diagnosis)))], [cases]);
  const visible = filter === "ALL" ? cases : cases.filter((item) => item.diagnosis === filter);
  const aggregate = summary?.aggregate;
  const open = async (id: string) => { setError(null); setRerun(null); try { setDetail(await api.evaluationCase(id, datasetId)); } catch (value) { setError(value); } };
  const rerunCase = async (id: string) => { setBusy(true); setError(null); try { setRerun(await api.rerunCase(id, datasetId)); } catch (value) { setError(value); } finally { setBusy(false); } };
  return <div className="page">
    <PageHeading eyebrow="Frozen evaluation artifacts" title="Evaluation" description="Browse the measured baseline, targeted-fix comparison, known failures, and single-case real reruns." />
    <section className="panel"><div className="section-title"><div><span className="eyebrow">Dataset</span><h2>Frozen evaluation version</h2></div><select aria-label="Evaluation dataset" value={datasetId} onChange={(event) => setDatasetId(event.target.value)}><option value="legal_eval_v1">Evaluation V1</option><option value="legal_eval_v2">Evaluation V2</option></select></div></section>
    <ErrorNotice error={error} />
    {!summary && !error && <div className="loading">Loading machine-readable evaluation reports…</div>}
    {summary && <>
      <div className="metric-grid evaluation-metrics"><Metric label="Cases" value={aggregate?.case_count} /><Metric label="Answerable" value={aggregate?.answerable_count} /><Metric label="Unanswerable" value={aggregate?.unanswerable_count} /><Metric label="Hit@10" value={pct(aggregate?.retrieval?.hit_at_10)} /><Metric label="MRR" value={pct(aggregate?.retrieval?.mrr)} /><Metric label="Context retention" value={pct(aggregate?.context?.expected_evidence_retention)} /><Metric label="Citation validity" value={pct(aggregate?.generation?.citation_structural_validity_rate)} /><Metric label="Correct abstention" value={pct(aggregate?.unanswerable?.correct_abstention_rate)} /></div>
      <section className="panel"><div className="section-title"><div><span className="eyebrow">Failure breakdown</span><h2>Measured classifications</h2></div><code>{summary.dataset_sha256.slice(0, 16)}…</code></div><div className="failure-row">{Object.entries(aggregate?.failure_counts ?? {}).map(([key, value]) => <button key={key} onClick={() => setFilter(key)}><StatusBadge value={key} /><strong>{String(value)}</strong></button>)}</div></section>
      <section className="panel"><div className="section-title"><div><span className="eyebrow">Case browser</span><h2>{visible.length} cases</h2></div><select aria-label="Failure filter" value={filter} onChange={(event) => setFilter(event.target.value)}>{diagnoses.map((item) => <option key={item}>{item}</option>)}</select></div>
        {!visible.length && <EmptyState>No evaluation cases match this failure filter.</EmptyState>}
        {!!visible.length && <div className="table-scroll"><table><thead><tr><th>Case</th><th>Category</th><th>Question</th><th>Answerable</th><th>Retrieval</th><th>Context</th><th>Generation</th><th>Diagnosis</th></tr></thead><tbody>{visible.map((item) => <tr key={item.case_id}><td><button className="link-button mono" onClick={() => open(item.case_id)}>{item.case_id}</button></td><td>{item.category}</td><td>{item.question}</td><td>{String(item.answerable)}</td><td>{item.retrieval_result}</td><td>{item.context_result}</td><td>{item.generation_result}</td><td><StatusBadge value={item.diagnosis} /></td></tr>)}</tbody></table></div>}
      </section>
      {comparison && <section className="panel"><span className="eyebrow">Before / after</span><h2>Targeted quality fixes</h2><MetricComparison before={comparison.before} after={comparison.after} /></section>}
      <section className="panel"><span className="eyebrow">Known limitations</span><h2>Not hidden by aggregate metrics</h2><ul className="limitations">{summary.known_limitations.map((item) => <li key={item}>{item}</li>)}</ul></section>
    </>}
    {detail && <div className="drawer-backdrop" onMouseDown={() => setDetail(null)}><aside className="drawer wide" role="dialog" aria-modal="true" aria-label="Evaluation case detail" onMouseDown={(event) => event.stopPropagation()}><div className="drawer-head"><div><span className="eyebrow">Evaluation case</span><h2>{caseId(detail)}</h2></div><button onClick={() => setDetail(null)}>Close</button></div><div className="comparison-grid"><section><h3>Expected</h3><JsonBlock value={detail.dataset_case} /></section><section><h3>Measured actual</h3><JsonBlock value={detail.measured_case} /></section></div><button className="primary" disabled={busy} onClick={() => rerunCase(caseId(detail))}>{busy ? "Running real pipeline…" : "Re-run this case"}</button>{rerun && <div className="notice neutral"><strong>Interactive rerun</strong><StatusBadge value={rerun.diagnosis ?? "NO_GROUND_TRUTH"} /><span>{rerun.generation.status} · {rerun.generation.citations.length} citations · {rerun.timings_ms.total_ms.toFixed(0)} ms</span></div>}</aside></div>}
  </div>;
}

function pct(value?: number) { return value == null ? "—" : `${(value * 100).toFixed(2)}%`; }

function caseId(detail: Record<string, unknown>) {
  const datasetCase = detail.dataset_case;
  if (!datasetCase || typeof datasetCase !== "object" || !("case_id" in datasetCase)) return "unknown";
  return String(datasetCase.case_id);
}

function MetricComparison({ before, after }: { before: EvaluationAggregate; after: EvaluationAggregate }) {
  const rows: Array<[string, number | undefined, number | undefined]> = [
    ["Hit@1", before.retrieval?.hit_at_1, after.retrieval?.hit_at_1], ["Hit@10", before.retrieval?.hit_at_10, after.retrieval?.hit_at_10], ["MRR", before.retrieval?.mrr, after.retrieval?.mrr],
    ["Citation validity", before.generation?.citation_structural_validity_rate, after.generation?.citation_structural_validity_rate], ["Missing citations", before.generation?.missing_citation_rate, after.generation?.missing_citation_rate], ["Expected source", before.generation?.expected_source_citation_match_rate, after.generation?.expected_source_citation_match_rate],
    ["Correct abstention", before.unanswerable?.correct_abstention_rate, after.unanswerable?.correct_abstention_rate], ["Unsupported answers", before.unanswerable?.unsupported_answer_rate, after.unanswerable?.unsupported_answer_rate],
  ];
  return <div className="table-scroll"><table><thead><tr><th>Metric</th><th>Before</th><th>After</th><th>Delta</th></tr></thead><tbody>{rows.map(([label, left, right]) => <tr key={String(label)}><td>{label}</td><td>{pct(left)}</td><td>{pct(right)}</td><td>{typeof left === "number" && typeof right === "number" ? `${((right-left)*100).toFixed(2)} pp` : "—"}</td></tr>)}</tbody></table></div>;
}
