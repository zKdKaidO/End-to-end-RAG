# Block 4 Phase 02 — Query embedding

Status: PASS

`QueryEmbedder` reuses the frozen `E5Embedder` singleton and its loaded `SentenceTransformer`; it is not instantiated per request. Query input is exactly `query: <query_text>`.

Verified by focused tests and one real-model smoke test:

- prefix is `query: `, never `passage: `;
- output shape is `(768,)`;
- every value is finite;
- L2 norm is approximately 1;
- 513-token input is rejected without calling model encoding;
- invalid dimensions, NaN output, and non-normalized output are rejected;
- singleton identity and Block 3 model object reuse are verified.

After API/PostgreSQL restart, the Hugging Face cache still contained 31 files and the first retrieval succeeded. Both API and indexing worker resolve the same Docker volume, `rag_model_cache`.
