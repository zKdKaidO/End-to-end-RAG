"""Read-only preflight for the user-supplied Corpus V2 PDFs."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "evaluation" / "corpus" / "input"
REPORT_DIR = ROOT / "evaluation" / "reports"
JSON_PATH = REPORT_DIR / "legal_corpus_v2_preflight.json"
MD_PATH = REPORT_DIR / "legal_corpus_v2_preflight.md"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_pdf(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "filename": path.name,
        "input_path": str(path.resolve()),
        "file_size": path.stat().st_size,
        "sha256": sha256(path),
        "readable_pdf": False,
        "page_count": None,
        "encrypted": False,
        "password_protected": False,
        "meaningful_text": False,
        "extracted_character_count": 0,
        "non_whitespace_character_count": 0,
        "pages_with_text": 0,
        "classification": "OTHER_ERROR",
        "error": None,
    }
    try:
        reader = PdfReader(path, strict=False)
        result["encrypted"] = bool(reader.is_encrypted)
        if reader.is_encrypted:
            try:
                unlocked = reader.decrypt("")
            except Exception:
                unlocked = 0
            if not unlocked:
                result["password_protected"] = True
                result["classification"] = "ENCRYPTED"
                return result

        result["readable_pdf"] = True
        result["page_count"] = len(reader.pages)
        texts: list[str] = []
        pages_with_text = 0
        for page in reader.pages:
            text = page.extract_text() or ""
            texts.append(text)
            if len("".join(text.split())) >= 20:
                pages_with_text += 1
        combined = "\n".join(texts)
        non_whitespace = len("".join(combined.split()))
        alphabetic = sum(char.isalpha() for char in combined)
        result["extracted_character_count"] = len(combined)
        result["non_whitespace_character_count"] = non_whitespace
        result["pages_with_text"] = pages_with_text
        minimum = max(500, int((result["page_count"] or 0) * 30))
        meaningful = non_whitespace >= minimum and alphabetic >= minimum // 2
        result["meaningful_text"] = meaningful
        result["classification"] = "READY" if meaningful else "TEXT_TOO_SPARSE_OR_SCAN_LIKE"
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        result["error"] = message[:1000]
        lowered = message.lower()
        result["classification"] = "INVALID_PDF" if "pdf" in lowered or "xref" in lowered else "OTHER_ERROR"
    return result


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Legal Corpus V2 PDF Preflight",
        "",
        f"Generated: {report['generated_at']}",
        "",
        f"Input directory: `{report['input_directory']}`",
        "",
        f"PDFs discovered: **{report['summary']['pdf_count']}**  ",
        f"READY: **{report['summary']['ready_count']}**  ",
        f"Excluded: **{report['summary']['excluded_count']}**",
        "",
        "No OCR was used. Text checks use native PDF extraction only.",
        "",
        "| File | Bytes | Pages | Encrypted | Extracted chars | Text pages | Classification |",
        "|---|---:|---:|---|---:|---:|---|",
    ]
    for item in report["files"]:
        lines.append(
            "| {filename} | {file_size} | {page_count} | {encrypted} | "
            "{extracted_character_count} | {pages_with_text} | **{classification}** |".format(**item)
        )
        if item["error"]:
            lines.extend(["", f"- `{item['filename']}` error: `{item['error']}`"])
    lines.extend(["", "## File hashes", ""])
    for item in report["files"]:
        lines.append(f"- `{item['filename']}`: `{item['sha256']}`")
    lines.extend(["", "## Classification rule", ""])
    lines.append(
        "A readable, unlocked PDF is READY when native extraction yields at least "
        "max(500 characters, 30 characters per page) and at least half that threshold is alphabetic."
    )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    pdfs = sorted(INPUT_DIR.glob("*.pdf"), key=lambda item: item.name.casefold())
    files = [inspect_pdf(path) for path in pdfs]
    ready = sum(item["classification"] == "READY" for item in files)
    report = {
        "report_id": "legal_corpus_v2_preflight",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_directory": str(INPUT_DIR.resolve()),
        "no_ocr": True,
        "summary": {
            "pdf_count": len(files),
            "ready_count": ready,
            "excluded_count": len(files) - ready,
            "classification_counts": {
                status: sum(item["classification"] == status for item in files)
                for status in (
                    "READY",
                    "TEXT_TOO_SPARSE_OR_SCAN_LIKE",
                    "ENCRYPTED",
                    "INVALID_PDF",
                    "OTHER_ERROR",
                )
            },
        },
        "files": files,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    MD_PATH.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
