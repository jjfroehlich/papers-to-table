# tasks.md — Paper Table Agent (v0.5)

UI/UX iteration with model-aware configuration and embedding/reranker support.

Conventions:
* “AC” = Acceptance Criteria
* Update README during implementation (not only at the end)

---

## P0 — Run + Settings UX

### [x] T0.1 Replace table upload with path + browse

**Work**
* Remove table file uploader from Run tab.
* Keep text path input with browse button and known tables helper.

**AC**
* Table input is path-driven with browse support; no upload control remains.

---

### [x] T0.2 LM Studio model registry + model-aware dropdowns

**Work**
* Fetch available model IDs from LM Studio and store in session state.
* Use registry-driven dropdowns for extraction, embedding, and reranking models.
* Surface warnings when selected models are not available.

**AC**
* Model dropdowns only list available LM Studio models and no longer offer unsupported defaults.

---

### [x] T0.3 Run-config aligned embedding/reranker backends

**Work**
* Extend run_config.json schema to include embedding/reranker model fields.
* Add embedding/reranker backend selection and model inputs in Settings/Run.
* Wire LM Studio embedding + reranking backends into retrieval/indexing.

**AC**
* `run_config.json` captures embedding and reranker backend/model choices and runs do not fail on unsupported defaults.

---

## P1 — Docs

### [x] T1.1 README + CHANGELOG update

**Work**
* Update README status, UI workflow, model setup instructions, and run_config guidance.
* Update CHANGELOG with user-facing configuration changes.

**AC**
* Docs reflect v0.5 UI and model-aware configuration.
