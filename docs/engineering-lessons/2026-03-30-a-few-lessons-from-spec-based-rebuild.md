## Engineering lessons (quick reference)

- **Symptom:** Highlight rectangles are off-text, off-page, or wrong after zoom.  
  **Cause:** Coarse parser block boxes and/or mismatched canvas-overlay coordinate systems.  
  **Fix:** Compute quote-level boxes from rendered page text; keep canvas and overlay in one coordinate space; use parser boxes only as approximate fallback.

- **Symptom:** Highlights appear on wrong pages or persist while browsing.  
  **Cause:** Highlight state not tied to the active evidence page.  
  **Fix:** Render highlights only on the evidence page; recompute/recenter on page, zoom, or evidence change.

- **Symptom:** “No coordinates” despite having evidence.  
  **Cause:** Model returned value without a usable quote anchor.  
  **Fix:** Add retrieval-backed evidence recovery; persist quote text + page + fallback state explicitly.

- **Symptom:** Proposed value, quote, and rationale feel inconsistent.  
  **Cause:** First model quote treated as primary without evidence ranking.  
  **Fix:** Rank evidence independently; choose explicit `primary_evidence`; retain ordered supporting evidence.

- **Symptom:** Reviewer cannot tell evidence vs inference.  
  **Cause:** Quotes and reasoning mixed in one block.  
  **Fix:** Separate direct quotes from reasoning/calculation in UI and data model.

- **Symptom:** Figure evidence often missing when useful.  
  **Cause:** Figure path only triggered in narrow fallback conditions.  
  **Fix:** Proactively scan all relevant figures when vision is available; allow figure evidence to supplement or rescue weak text outcomes.

- **Symptom:** Figure evidence adds noise/contradictions.  
  **Cause:** Figure outputs appended without consistency checks.  
  **Fix:** Append figure evidence only when it supports current best answer; label figure-derived support clearly.

- **Symptom:** PDF viewer exists but review is still slow/error-prone.  
  **Cause:** Viewer treated as static preview.  
  **Fix:** Add reviewer controls: prev/next page, jump-to-page, zoom, evidence focus, and figure-to-full-page navigation.

- **Symptom:** Vision behavior is flaky across runs.  
  **Cause:** Single model assumed for both text and image tasks.  
  **Fix:** Support separate text and vision models in config; show both in run summaries/context for debugging and trust.