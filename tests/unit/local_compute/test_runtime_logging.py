from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _run_no_console_script(
    code: str, *arguments: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code, *arguments],
        text=True,
        capture_output=True,
        check=False,
    )


def test_structlog_default_reproduces_the_windowed_none_stream_failure():
    """Keep the pre-fix failure mechanism explicit and data-free."""
    result = _run_no_console_script(
        "import sys\n"
        "sys.stdout = None\n"
        "sys.stderr = None\n"
        "import structlog\n"
        "try:\n"
        "    structlog.get_logger('no_console_regression').info('context_build_started', stage='VALIDATE_INPUT')\n"
        "except Exception as exc:\n"
        "    sys.__stdout__.write(type(exc).__name__ + ':' + str(exc))\n"
    )

    assert result.returncode == 0
    assert result.stdout == "TypeError:cannot create weak reference to 'NoneType' object"


def test_local_compute_file_logger_and_context_builder_work_without_standard_streams(
    tmp_path: Path,
):
    log_directory = tmp_path / "logs"
    result = _run_no_console_script(
        "import sys\n"
        "sys.stdout = None\n"
        "sys.stderr = None\n"
        "from pathlib import Path\n"
        "from app.local_compute.runtime_logging import configure_local_compute_logging\n"
        "configure_local_compute_logging(Path(sys.argv[1]))\n"
        "from app.context.service import ContextBuilderService\n"
        "class Counter:\n"
        "    provider = 'fixture'\n"
        "    tokenizer_id = 'fixture'\n"
        "    def count(self, value): return len(value.split())\n"
        "candidate = {\n"
        " 'chunk_id':'00000000-0000-0000-0000-000000000001',\n"
        " 'document_id':'00000000-0000-0000-0000-000000000002',\n"
        " 'content_text':'Synthetic evidence',\n"
        " 'metadata_json':{}, 'provenance_json':{},\n"
        " 'dense_score':0.9, 'dense_rank':1, 'lexical_score':None, 'lexical_rank':None,\n"
        " 'fusion_score':0.02, 'final_rank':1\n"
        "}\n"
        "package = ContextBuilderService(Counter()).build(\n"
        " request_id='no-console-context', query_text='synthetic query',\n"
        " retrieved_candidates=[candidate], context_budget_tokens=100)\n"
        "assert package.selected_count == 1\n"
        "sys.__stdout__.write('PASS')\n",
        str(log_directory),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "PASS"
    log_text = (log_directory / "application.jsonl").read_text(encoding="utf-8")
    assert "context_build_started" in log_text
    assert "context_build_completed" in log_text
