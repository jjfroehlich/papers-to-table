# Papers-To-Table Agent Kit

`skills/papers-to-table-agent-kit/` is a portable skill for capable agents that need to extract structured tables or write research reports from PDFs without running the local app.

This is based on principles learned from building this app, but is an independent and portable skill for your agent of choice (Codex, Claude, Hermes, etc). It just provides some guidance, an optional human-review html, and doesnt require a local app or local LLM provider. It lets an agent intentionally do the extraction using any of its tools and capabilities. 

## Use Cases

Agents can use this skill when the task is to:

- extract useful structured tables from one or several scientific PDF files without installing the local app
- create a table as a working artifact for a research report or literature review
- generate a lightweight static browser review package with values, evidence, and rationale
- collect information from PDF files and provide a human review interface

## Installation

Just tell your agent, for example `install the skill at https://github.com/jjfroehlich/papers-to-table/tree/main/skills/papers-to-table-agent-kit/`. Alternatively, copy `skills/papers-to-table-agent-kit/` into your agent system's skill directory. Keep the `references/`, `scripts/`, and `templates/` files with it.