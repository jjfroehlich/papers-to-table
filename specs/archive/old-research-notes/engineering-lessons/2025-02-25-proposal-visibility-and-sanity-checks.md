## Lesson
Silent proposal drop-offs are easy to miss when extraction succeeds but review shows “none.” A lightweight run-level sanity check plus internal proposal/verification count logs make it obvious when proposal persistence fails versus when UI filtering hides items.

## Impact
- We now flag runs as FAILED when matched PDFs and extractable columns exist but proposals == 0.
- Debug logs summarize proposal and verification counts by status, making UI/DB mismatches visible.

## Durable rule?
Yes: add a run-level sanity check anytime a pipeline stage could silently produce zero records while upstream signals success. Consider documenting this as a standard health check in future runbooks.
