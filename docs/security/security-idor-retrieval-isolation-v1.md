# IDOR and Retrieval Isolation V1

Controlled Alice/Bob/admin fuzzing covered documents, ingestion/processing/indexing jobs, chat sessions, chat turns, retrieval scope, answers, source mapping, debug and evaluation routes. Existing-but-unauthorized identifiers and random identifiers produce the same `404 RESOURCE_NOT_FOUND`; admin is not an implicit private-document reader.

Three Alice-only documents used overlapping legal names and topics as canaries. Bob's dense candidates, lexical candidates, RRF/hierarchy results, hydrated chunks, Block 5 context, answers and citations contained zero Alice canaries. Mixed explicit scope containing one authorized and one unauthorized document was rejected before retrieval; the retrieval service invocation count remained zero. Direct injection of Alice's document UUID was likewise rejected.

Static and runtime audits found zero authorization predicates based on `documents.user_id`. Access uses grants plus the explicitly Global corpus. No remediation of frozen ranking, hierarchy, context building, or provenance mapping was necessary.
