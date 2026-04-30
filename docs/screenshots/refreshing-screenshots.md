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
The screenshot test spins up a deterministic local backend and frontend stack, captures the documentation images, and writes them into `docs/screenshots/`.