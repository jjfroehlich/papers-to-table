## Evidence + review resilience

**Issue:** proposals were vulnerable to being dropped or rendered unreviewable when evidence was missing or highlights could not be resolved, and completed runs weren’t reliably discoverable in Review.

**Fix:** always persist one proposal record per column (even unclear/no_evidence), enforce “no proposed value without quote+page,” cache highlight rectangles in the DB, and mark runs as completed with an explicit marker so the Review dropdown can list finished runs deterministically.

**Impact:** review now consistently surfaces every target column and provides a clear needs_more_evidence signal when highlights fail, without re-running extraction or rescanning PDFs.

**Takeaway:** treat evidence resolution and run completion as first-class persisted state—never as UI-derived or best-effort computations.
