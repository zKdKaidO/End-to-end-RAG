# PostgreSQL and MinIO consistency V1

PostgreSQL is authoritative for document identity, hashes, access grants, processing state, chunks, and indexes. MinIO is authoritative for immutable source-PDF bytes. The canonical mapping is `<document UUID>/original.pdf`.

Cross-store mutations take a shared advisory lock; paired backup takes the exclusive form. Reconciliation classifies every reference as `HEALTHY`, `MISSING_OBJECT`, or `HASH_MISMATCH`, and independently reports `ORPHAN_OBJECT`. Missing or mismatched canonical data blocks readiness. An orphan is a warning because deleting it automatically could destroy recoverable data.

PostgreSQL-only recovery may reuse the surviving MinIO store only when its complete key/hash map exactly equals the selected backup manifest. MinIO-only recovery restores the paired objects while PostgreSQL is restored from the same backup. Mixing timestamps is rejected.

Topical application state is never reconstructed from object names alone, and Python-side filtering is not used as a substitute for durable authorization or retrieval scoping.
