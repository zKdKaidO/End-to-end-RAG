"""Capture representative Evaluation V2 reruns through the Debug Cockpit HTTP API."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "evaluation" / "reports" / "legal_eval_v2_baseline.json"
OUTPUT = ROOT / "evaluation" / "reports" / "legal_eval_v2_debug_samples.json"
CASES = (
    "v2_bank_board_loan_threshold",       # WRONG_DOCUMENT
    "v2_social_scope",                    # RETRIEVAL_MISS
    "v2_social_practice_content",         # PARTIAL_MULTI_EVIDENCE_RETRIEVAL
    "v2_civil_scope",                     # FALSE_ABSTENTION
    "v2_cross_document_effective_dates",  # difficult PASS / multi-document
)


def main() -> None:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    measured = {item["case_id"]: item for item in baseline["cases"]}
    samples = []
    for index, case_id in enumerate(CASES, start=1):
        print(f"[{index}/{len(CASES)}] {case_id}", flush=True)
        url = (
            f"http://localhost:8001/internal/evaluation/cases/{case_id}/rerun"
            "?dataset_id=legal_eval_v2"
        )
        request = Request(url, method="POST")
        with urlopen(request, timeout=240) as response:
            trace = json.loads(response.read().decode("utf-8"))
        samples.append(
            {
                "case_id": case_id,
                "baseline_failure_attribution": measured[case_id]["failure_attribution_v2"],
                "debug_trace": trace,
            }
        )
    output = {
        "report_id": "legal_eval_v2_debug_samples",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "REAL_INTERNAL_DEBUG_COCKPIT_HTTP_RERUN",
        "generation_wrong_source_sample": "NOT_AVAILABLE_IN_V2_BASELINE",
        "samples": samples,
    }
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "PASS", "sample_count": len(samples), "path": str(OUTPUT)}))


if __name__ == "__main__":
    main()
