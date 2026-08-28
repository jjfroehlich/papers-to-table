## Refreshing Screenshots

From the repo root:

```bash
cd app
python -m pip install -e ./backend[test]
cd frontend
npm install
cd ../..
python -m playwright install chromium
python -m pytest app/tests/e2e/test_doc_screenshots.py -m e2e --capture-doc-screenshots
```
These commands assume you start in the repository root. If you are already inside `app/` or `app/frontend/`, adjust the `cd` steps before running them.
The screenshot test spins up a deterministic local backend and frontend stack, captures the current documentation images, and writes them into `docs/screenshots/`. It also verifies the current labels and controls used to reach each captured state, so UI text changes that make the capture flow stale fail explicitly instead of silently preserving old screenshots.

`agent-kit-review-workspace.png` is the separate portable Agent Kit interface. Refresh it from a validated run built with `skills/papers-to-table-agent-kit/scripts/build_review_package.py --with-review`, serve the generated `human_review/` directory over localhost, and capture a `1440 × 1000` viewport with a proposal and its PDF evidence visible. Use a checked-in benchmark PDF and source-accurate evidence so the documentation image remains reproducible and truthful.
