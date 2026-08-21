# Legal Corpus V2 Integrity Audit

Generated: 2026-08-19T12:29:43.892989+00:00

Corpus integrity: **PASS**

## Scale

- Supplied PDFs: 5
- READY: 3
- Excluded: 2
- Successfully ingested: 3
- Pages: 105
- Legal units: 951
- Chunks: 965
- Chunk indexes: 965
- Average chunks/document: 321.67
- Min/max chunks/document: 121/692
- Public PostgreSQL tables: 10
- Database size: 41500007 bytes

## Document integrity

| Document key | Document ID | Pages | Units | Chunks | Indexes | Status |
|---|---|---:|---:|---:|---:|---|
| social_work_practice_2026 | `3fb22b9b-ed46-4e04-97e2-b8c854f8252b` | 18 | 115 | 121 | 121 | **PASS** |
| people_credit_fund_safety_40_2026 | `78e54e57-fc2e-47b2-919c-c7120776226d` | 21 | 150 | 152 | 152 | **PASS** |
| civil_servants_consolidated_10_2026 | `ed9f3e56-f3cd-41f6-9ed9-8b70e7f44c25` | 66 | 686 | 692 | 692 | **PASS** |

## Diversity

- Three distinct domains are present: social work practice, people-credit-fund safety, and civil-service management.
- All three documents contain repeated structural identifiers such as Điều 1, Điều 2, khoản 1, and effective-date clauses, supporting document-disambiguation and same-article-number tests.
- The consolidated civil-service instrument contains many amendment footnotes and repeated effective-date language, supporting near-duplicate/ambiguity stress cases within one document.
- The corpus supports cross-document terminology stress (authority, applicability, reporting, effective date), but does not provide a defensible substantive rule that inherently requires combining two different legal domains.
- The three documents differ strongly in length (121, 152, and 692 chunks), enabling scale and deeper-rank stress without manufacturing categories.

## Duplicate observations

- Duplicate supplied PDF hashes: 0
- Exact duplicate chunk groups: 4
- Potential cross-document near-duplicate pairs: 25
- Method: Nearest cross-document embedding cosine similarity >= 0.92; diagnostic signal only, not legal equivalence.

The automatic Block 2 indexing hook initially produced legacy `v1` labels. The existing canonical indexing API was then used, without code changes, to persist the frozen `block3-v1` contract required by Block 4.
