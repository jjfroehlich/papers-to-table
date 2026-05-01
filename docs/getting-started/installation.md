# Installation

## Main app and companion apps

Start by choosing a folder, fetching the repository, and changing into the repo root. 

```bash
cd /path/to/your/workspace
git clone https://github.com/jjfroehlich/papers-to-table.git papers-to-table
cd papers-to-table
```

Install from the repo root:

```bash
python scripts/papers_to_table.py install
```

This installs backend, frontend, eval, and optimizer, with dependencies. It also upgrades `pip`, runs `npm audit fix` for the frontend, and fails if `npm audit --audit-level=moderate` still finds a moderate-or-worse vulnerability.

The install command also creates `app/config.json` from `app/config.example.json` when no local config exists. The four operator paths are left blank so browser mode can start immediately and you can select the table, schema, PDF files, and output directory in the interface.

Start browser mode:

```bash
python scripts/papers_to_table.py review
```

Open `http://127.0.0.1:5173`, choose the paths in the Run setup panel, then click **Start run**. The backend runs preflight first; if readiness passes it continues into extraction.

## Compile Documentation

Use this only for compiling or serving the local Documentation manual.

```bash
python -m pip install -r tools/docs/requirements.txt
```
