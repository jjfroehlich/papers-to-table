# Refined SVG schematics

Generated from `make_refined_svg_schematics.py` as canonical documentation figures.

Figure style:

- Frameless canvases with no slide footer, sized per schematic for insertion into reports or docs.
- Neutral connector linework; arrowheads are explicit vector shapes for Illustrator compatibility.
- Icons are custom SVG symbols drawn in a Lucide-style stroke system with centered backplate alignment.
- Text uses standard `bold` / `normal` SVG weights so Illustrator preserves hierarchy better.

Included:

- `00_icon_library.svg` / `.png`: updated reusable icon set with revised report, benchmark, settings, bundle, and document icons.
- `01_readme_overview_refined.svg` / `.png`: README-level workflow schematic.
- `02_main_app_lifecycle_refined.svg` / `.png`: detailed main-app lifecycle schematic.
- `03_orchestrator_eval_benchmark_refined.svg` / `.png`: candidate-settings-driven optimizer sweep with app runs, run bundles, eval scoring with gold data, score results, and HTML reports.
- `04_agent_skills_refined.svg` / `.png`: compact two-box agent skill workflow figure.

Icon basis:

- Simple geometry, round caps/joins, consistent density, and restrained backplates.
- Lucide is ISC-licensed; the design guide was used as the icon consistency reference rather than vendoring a full external icon package.

Companion-tools semantics:

- Optimizer sweeps over candidate settings: run the main app, collect run bundles, evaluate against benchmark/gold data, score each candidate, and emit HTML reports.
- Eval is scoring-only: it can score optimizer-produced run bundles, ordinary run bundles, or external filled tables against gold data.
- `papers-to-table-local-app` skill is app-backed: an agent uses the installed local app headlessly and may auto-accept/export values without human review.
- `papers-to-table-agent-kit` is portable and standalone: it borrows the app's schema/evidence/review/export principles but does not require the local app or LM Studio.

Intentionally omitted from this refined set:

- Standalone run-bundle schematic: not needed for the current docs plan.
- Review-workspace schematic: use a real review UI screenshot instead.
