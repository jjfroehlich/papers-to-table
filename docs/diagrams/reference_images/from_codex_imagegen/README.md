# Image-generated concept drafts

These are raster concept drafts generated with the built-in image generation tool.
They are intended for visual direction, not final text fidelity. Exact labels and
implementation details should be carried back into the editable SVG versions.

## Files

- `01_readme_overview_concept.png` - README-level promise and visual language.
- `02_main_app_lifecycle_concept.png` - Swimlane architecture/lifecycle.
- `03_run_bundle_contract_concept.png` - Run bundle as file contract.
- `04_review_workspace_evidence_concept.png` - Review UI and evidence workspace.
- `05_companion_tools_ecosystem_concept.png` - Companion tools around the run bundle.

## Design takeaways

- The README concept has the strongest first-glance story: numbered stages,
  private/local boundary, and bottom value-strip are worth porting into SVG.
- The lifecycle concept has a cleaner swimlane structure than the first SVG:
  use tall lane headers, larger icons, and a bottom canonical-record banner.
- The run-bundle concept is the strongest artifact diagram: use the large
  folder/file-cabinet metaphor and route consumers from one guarded contract.
- The review workspace concept is the best UI reference: keep the three-panel
  browser layout, status tabs, large proposed value, evidence quote, and clear
  decision buttons.
- The companion-tools concept is a useful hub map, but the SVG version should
  stay simpler and avoid overusing badge text.

## Prompt summaries

- README overview: wide software-doc infographic showing PDFs/table/schema
  entering private local processing, proposals, human review, and accepted export.
- Main app lifecycle: four swimlanes for setup, document preparation, extraction
  engine, and review/export, including optional rescue, vision, and selection.
- Run bundle contract: large run-bundle directory/folder on the left with
  Review UI, Eval, and Optimizer consumers on the right.
- Review workspace: high-fidelity browser mockup with proposal queue, proposal
  detail/decision panel, and PDF/evidence inspector.
- Companion ecosystem: central Main App and Run Bundle with Inputs, Reviewed
  outputs, Eval, Optimizer, and Agent Skills as connected cards.
