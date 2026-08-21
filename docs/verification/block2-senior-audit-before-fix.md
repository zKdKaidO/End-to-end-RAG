# BLOCK 2 SENIOR AUDIT - BEFORE FIX

## AUDIT 1 - REPROCESSING DATA INTEGRITY
**Files inspected**: `app/repositories/processing_repo.py`
**Functions inspected**: `save_reconstruction`, `save_units_and_chunks`
**Current behavior**: 
`save_reconstruction` deletes old reconstructions and commits. Then `save_units_and_chunks` deletes old chunks, deletes old units, inserts new ones, and commits.
**Evidence**: The transactions are split. If `save_units_and_chunks` fails, the DB is left in a partial state. Also, chunk deletion and unit deletion are sequential without atomic bounding with reconstruction deletion.
**PASS / FAIL**: FAIL
**Reason**: Split transactions cause lack of atomicity and could leave stale records if one stage fails.

## AUDIT 2 - HEADER / FOOTER SAFETY
**Files inspected**: `app/processing/header_footer.py`
**Functions inspected**: `remove_headers_footers`
**Current behavior**: The algorithm limits candidate search to `lines[:check_lines]` and `lines[-check_lines:]`. It requires `v / num_pages >= frequency_threshold` (0.5).
**Evidence**: If a document has only 2 pages, `1 / 2 = 0.5`. Thus, ANY unique text line at the top or bottom of a page in a 2-page document is falsely identified as a header/footer and removed.
**PASS / FAIL**: FAIL
**Reason**: Mathematical edge case for small documents (N=2) causes false positive removal of valid structural text at page boundaries.

## AUDIT 3 - RQ RETRY POLICY
**Files inspected**: `app/queue/rq_client.py`, `docker-compose.yml`, `app/processing_worker_main.py`
**Functions inspected**: `enqueue_document_processing_job`
**Current behavior**: Enqueue uses `Retry(max=2, interval=[2, 5])`. Installed RQ version is `2.11.0`, which correctly maps `interval` to `intervals` under the hood. The worker is started with `worker.work(with_scheduler=True)`.
**Evidence**: `rq.Retry` constructor handles backwards compatibility. `with_scheduler=True` enables delayed retries.
**PASS / FAIL**: PASS
**Reason**: The configuration accurately implements bounded delayed retries using RQ's native mechanisms.

## AUDIT 4 - GRANULAR CURRENT_STAGE OBSERVABILITY
**Files inspected**: `app/processing_worker_main.py`, `app/repositories/processing_job_repo.py`
**Functions inspected**: `process_document`, `update_stage`
**Current behavior**: Before each major processing step, `repo.update_stage()` is called. `update_stage` runs a dedicated `self.db.commit()`.
**Evidence**: The database transaction is committed before the heavy processing begins, ensuring visibility to external observers immediately.
**PASS / FAIL**: PASS
**Reason**: Stage updates are committed granularly.

## AUDIT 5 - RETRY CLASSIFICATION
**Files inspected**: `app/processing_worker_main.py`
**Functions inspected**: `process_document`
**Current behavior**: `except Exception as e:` catches all exceptions and raises them for RQ to retry if `retries_left > 0`.
**Evidence**: Deterministic errors like `ValueError`, `TypeError`, or parser-specific exceptions will be retried up to 2 times, wasting resources and violating the bounded retry semantics for non-transient errors.
**PASS / FAIL**: FAIL
**Reason**: No distinction between transient (e.g. OperationalError, RedisError) and deterministic exceptions.

## AUDIT 6 - GOLDEN TRUTH INDEPENDENCE
**Files inspected**: `tests/fixtures/sample_legal_expected.json`
**Functions inspected**: `test_metadata_extraction`
**Current behavior**: The expected fixture was manually authored by inspecting the raw text dump of the PDF. It contains metadata fields. It does not contain auto-generated legal units.
**Evidence**: The fixture was written independently, satisfying independence. However, it only evaluates metadata.
**PASS / FAIL**: PASS
**Reason**: The fixture was independently created without relying on parser output.

## AUDIT 7 - FAILURE ATOMICITY
**Files inspected**: `app/repositories/processing_repo.py`, `app/processing_worker_main.py`
**Functions inspected**: `save_reconstruction`, `save_units_and_chunks`
**Current behavior**: Same as Audit 1. `save_reconstruction` commits independently of `save_units_and_chunks`.
**Evidence**: If a failure occurs during `save_units_and_chunks`, the reconstruction is updated but the chunks/units are not, leaving an invalid partial state.
**PASS / FAIL**: FAIL
**Reason**: Persistence is not completely atomic across all three derived tables.
