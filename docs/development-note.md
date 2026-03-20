# Development note

Paper Table Agent is a local-first staged workflow application.

Canonical pipeline stages:
1. validate config and create run bundle
2. load table and schema
3. parse PDFs into normalized parsed-document artifacts
4. match PDFs to rows
5. build per-column style profiles and retrieval chunks
6. generate one proposal per eligible cell with evidence
7. review proposals in the browser UI
8. export accepted changes to a new XLSX plus audit log
