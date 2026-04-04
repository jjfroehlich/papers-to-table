# Compounding lesson: audit proposals must be isolated end-to-end

When adding audit-mode extraction, ensure audit proposals are explicitly flagged and excluded from export paths. This prevents accidental overwrite of filled cells even if a reviewer accepts a diagnostic proposal. Pairing that flag with evaluation outputs (proposal_eval.json + run_report summary updates) keeps audit workflows safe, traceable, and measurable without affecting production data.
