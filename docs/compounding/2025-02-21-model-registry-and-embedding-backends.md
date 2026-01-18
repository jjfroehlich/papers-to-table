## Model registry + embedding backend alignment

**Issue:** the UI exposed embedding/reranker choices that were not supported by the backend, leading to runtime `Unsupported embedding backend` failures when runs started.

**Fix:** align UI dropdowns with the run configuration and LM Studio model registry, add explicit backend/model fields for embeddings and reranking, and validate selections before starting a run.

**Impact:** runs no longer fail due to unsupported defaults, and model selection stays consistent with what LM Studio actually has loaded.

**Takeaway:** keep UI model selectors in lockstep with backend capabilities and validate run-critical configuration before execution.
