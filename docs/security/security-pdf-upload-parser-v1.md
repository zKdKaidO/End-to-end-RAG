# PDF Upload and Parser Security V1

## Red team

Pre-hardening upload read the whole request, checked size after buffering, and accepted any byte stream beginning `%PDF-`. There were no MIME, filename, encryption, structural, page-count, extracted-text, worker resource, or job-time bounds.

## Blue team

Uploads are read in bounded 64 KiB chunks and rejected immediately over the configured size. Validation requires a safe NFC `.pdf` filename, `application/pdf`, PDF magic, successful PyMuPDF structural open, at least one page, no password/encryption, and at most 1,000 pages. Extraction rechecks structure and enforces per-page (2,000,000 chars) and total (20,000,000 chars) text caps. Malformed, truncated, disguised, encrypted, punctuation/path filenames, high-page, oversized and compressed-repetition fixtures fail safely.

RQ timeouts are 1,800 s for ingestion and 3,600 s for processing/indexing. Compose bounds ingestion workers at 1 GiB/1 CPU/256 PIDs, processing at 2 GiB/1.5 CPU/256 PIDs, and indexing at 4 GiB/2 CPU/512 PIDs, all with restart policy.

A controlled PDF with an external URI was parsed while a local observation server recorded zero requests. Processing/indexing workers are attached only to the internal backend network: internal Redis works, while public DNS/HTTPS egress fails. Application health remained `200` after all fixtures.
