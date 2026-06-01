# Vendored PDF.js assets

`pdf.mjs` and `pdf.worker.mjs` in this directory are vendored from Mozilla [PDF.js](https://github.com/mozilla/pdf.js), distributed on npm as [`pdfjs-dist`](https://www.npmjs.com/package/pdfjs-dist).

- Exact package version: `pdfjs-dist@5.6.205`
- Source path used to copy these files: `app/frontend/node_modules/pdfjs-dist/build/pdf.mjs` and `app/frontend/node_modules/pdfjs-dist/build/pdf.worker.mjs`
- Upstream license: Apache-2.0 (`./LICENSE`)

## Why these files are vendored

The review bundle builder for the agent kit copies PDF.js runtime assets into generated review packages. Keeping a checked-in copy here makes that packaging step self-contained even when `app/frontend/node_modules` is unavailable, and avoids changing the external-agent authoring contract for review bundles.

## How to refresh

1. Update the `pdfjs-dist` version used by `/tmp/workspace/jjfroehlich/papers-to-table/app/frontend/package.json` if needed.
2. Install frontend dependencies so `app/frontend/node_modules/pdfjs-dist/` contains the target version.
3. Copy `app/frontend/node_modules/pdfjs-dist/build/pdf.mjs` to `skills/papers-to-table-agent-kit/assets/pdfjs/pdf.mjs`.
4. Copy `app/frontend/node_modules/pdfjs-dist/build/pdf.worker.mjs` to `skills/papers-to-table-agent-kit/assets/pdfjs/pdf.worker.mjs`.
5. Confirm the version header in both vendored files still matches this README, and update this file if the version or source path changes.
6. Keep `skills/papers-to-table-agent-kit/assets/pdfjs/LICENSE` aligned with the upstream PDF.js package/repository license text.
7. Re-run the relevant validations for the agent kit before merging.
