# Main Installation

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

This installs backend, frontend, eval, and optimizer, with dependencies.

## Compile Documentation Pages

Use this only when building or serving the local static manual.

```bash
python -m pip install -r tools/docs/requirements.txt
```