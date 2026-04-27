# Current status and backlog

## Verified current status

- [x] Main app has one central repo-level command surface for install, review startup, preflight, and headless use
- [x] Headless mode supports explicit `--accept-all` and rejects unattended export when review is still pending
- [x] Headless auto-accept is recorded in decision artifacts and reviewer summaries
- [x] Eval is packaged as an installable companion CLI
- [x] Optimizer has an explicit canonical `optimize_one_model.json` preset alongside compare and overnight presets
- [x] README and docs now expose one clear install/run/navigation path
- [x] Integrated current truth now exists in `specs/spec.md`
- [x] Docs are now buildable as a local/static MkDocs Material manual
- [x] Repo command surface includes docs serve/build wrappers
- [x] Reusable headless agent skill exists under `agent-skills/papers-to-table/`

## Current backlog

- [ ] Continue removing personal-path assumptions from real benchmark preset examples
- [ ] Refresh screenshots when the next visible UI workflow change lands
- [ ] Keep supporting modular spec references aligned with the integrated spec as behavior evolves
