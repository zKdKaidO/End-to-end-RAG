from pathlib import Path


def _pct(value):
    return "n/a" if value is None else f"{value * 100:.2f}%"


def render_markdown(report: dict) -> str:
    aggregate = report["aggregate"]
    retrieval = aggregate["retrieval"]
    context = aggregate["context"]
    generation = aggregate["generation"]
    unanswerable = aggregate["unanswerable"]
    lines = [
        "# Legal RAG Evaluation V1 — Baseline Measurement",
        "",
        "> This is a measured baseline. Recommended thresholds are not enforced.",
        "",
        "## Dataset",
        "",
        f"- Cases: {aggregate['case_count']} ({aggregate['answerable_count']} answerable, {aggregate['unanswerable_count']} unanswerable)",
        f"- Categories: {aggregate['categories']}",
        f"- Dataset validation: {report['dataset_validation']['status']}",
        "",
        "## Measured results",
        "",
        f"- Retrieval Hit@1 / @3 / @5 / @10: {_pct(retrieval['hit_at_1'])} / {_pct(retrieval['hit_at_3'])} / {_pct(retrieval['hit_at_5'])} / {_pct(retrieval['hit_at_10'])}",
        f"- Retrieval MRR: {retrieval['mrr']:.4f}",
        f"- Context expected-evidence retention: {_pct(context['expected_evidence_retention'])}",
        f"- Citation presence: {_pct(generation['citation_presence_rate'])}",
        f"- Citation structural validity: {_pct(generation['citation_structural_validity_rate'])}",
        f"- Expected-source citation match: {_pct(generation['expected_source_citation_match_rate'])}",
        f"- Invalid / missing citation rate: {_pct(generation['invalid_citation_rate'])} / {_pct(generation['missing_citation_rate'])}",
        f"- Correct abstention / unsupported answer rate: {_pct(unanswerable['correct_abstention_rate'])} / {_pct(unanswerable['unsupported_answer_rate'])}",
        f"- Failure counts: {aggregate['failure_counts']}",
        "",
        "## Latency",
        "",
        "| Stage | Mean ms | P50 ms | P95 ms | N |",
        "|---|---:|---:|---:|---:|",
    ]
    for stage, values in aggregate["latency"].items():
        def number(value):
            return "n/a" if value is None else f"{value:.2f}"
        lines.append(
            f"| {stage} | {number(values['mean_ms'])} | {number(values['p50_ms'])} | {number(values['p95_ms'])} | {values['count']} |"
        )
    lines.extend(
        [
            "",
            "## Recommended gate thresholds",
            "",
            "These are recommendations only and are **not enforced**. The first recommendation is a no-regression gate against this measured baseline; independent production-readiness thresholds require human review and a broader corpus.",
            "",
            "```json",
            __import__("json").dumps(aggregate["recommended_gate_thresholds"], ensure_ascii=False, indent=2),
            "```",
            "",
            "## Per-case reports",
            "",
        ]
    )
    for case in report["cases"]:
        b4, b5, b6, metrics = case["block4"], case["block5"], case["block6"], case["metrics"]
        lines.extend(
            [
                f"### {case['case_id']} — {case['category']}",
                "",
                f"- Question: {case['question']}",
                f"- Answerable: {case['answerable']}",
                f"- Expected evidence: {case['acceptable_evidence_sets']}",
                f"- Block 4 final chunks/ranks: {[(item['chunk_id'], item['final_rank']) for item in b4['final_candidates']]}",
                f"- Expected solution rank: {metrics['expected_evidence_rank']}",
                f"- Retrieval result: {'FOUND' if metrics['retrieval_found'] else 'MISS'}",
                f"- Block 5 selected: {list(zip(b5['selected_source_ids'], b5['selected_chunk_ids']))}",
                f"- Context tokens: {b5['context_token_count']} / {b5['context_budget_tokens']}; stop={b5['stop_reason']}",
                f"- Expected evidence retained: {metrics['context_retained']}",
                f"- Block 6: {b6['status']}; citation validation={b6['citation_validation']}",
                f"- Answer preview: {b6['answer_text'][:400]}",
                f"- Citations / expected-source match: {b6['mapped_chunk_ids']} / {metrics['expected_source_match']}",
                f"- Failure attribution: {case['failure_attribution'] or 'PASS'}",
                f"- Timings ms: {case['timings']}",
                "",
            ]
        )
    lines.extend(
        [
            "## Metric semantics and limitations",
            "",
            "An acceptable evidence solution is found only when every chunk in at least one acceptable set occurs within K; its rank is the lowest possible maximum member rank. MRR uses that solution rank. Context retention uses the same complete-set rule. Expected-source citation match is separate from structural citation validity and also requires a complete acceptable set. No LLM-as-judge or semantic entailment claim is made.",
            "",
            "The indexed evaluation corpus contains one substantive legal document. Dataset breadth and all aggregate estimates are therefore limited and require human review before any production gate is approved.",
            "",
        ]
    )
    return "\n".join(lines)


def write_markdown(path: str | Path, report: dict) -> None:
    Path(path).write_text(render_markdown(report), encoding="utf-8")
