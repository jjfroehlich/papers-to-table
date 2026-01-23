# plan.md — Paper Table Agent (simplified product execution plan)

Phased implementation plan for the simplified “best possible extraction + simple review” product.
Each phase includes acceptance checks aligned with the v0.7 spec.

## Phase P0 — Proposals appear + review works end-to-end (stub providers)

**Focus**
- Stub LLM + stub embeddings/reranker to run without external providers.
- Minimal UI: Run + Review only, matched rows, pending-only review queue.
- Run-level sanity checks for zero-proposal failures with diagnostics.

**Acceptance checks**
- CLI run with stub settings produces proposals for matched rows.
- Review UI loads a run and shows at least one proposal with evidence.
- run_report marks FAILED on matched-but-zero-proposals and records diagnostics.

---

## Phase P1 — Real provider integration + retrieval pipeline

**Focus**
- LM Studio/Ollama/OpenAI-compatible providers and dense retrieval when configured.
- BEST retrieval preset with HyDE + multi-query + RRF + rerank fallback.
- Robust evidence validation and retry-on-unclear behavior.

**Acceptance checks**
- Real providers work with the same config file as stub mode.
- Retrieval falls back cleanly to BM25/TF-IDF when dense backends are missing.

---

## Phase P2 — OCR/GROBID improvements (config-only)

**Focus**
- Automatic OCR/GROBID triggering under config control (no UI knobs).
- Improved diagnostics for scanned PDFs and text sparsity.

**Acceptance checks**
- OCR/GROBID paths are configurable and recorded in run_report diagnostics.
