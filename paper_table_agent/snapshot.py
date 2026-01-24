from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import textwrap
import zipfile
from dataclasses import dataclass
from pathlib import Path
from types import UnionType
from typing import Any, Iterable, Union, get_args, get_origin

from importlib import metadata
from pydantic import BaseModel

from paper_table_agent import __version__
from paper_table_agent.config import (
    ExtractionConfig,
    GrobidConfig,
    MatchingConfig,
    OcrConfig,
    OutputConfig,
    ProviderConfig,
    RetrievalConfig,
    RunConfig,
)

DEFAULT_SNAPSHOT_DIR = Path("runs/_diagnostics/latest_snapshot")


@dataclass(frozen=True)
class SnapshotModule:
    path: str
    purpose: str


def write_snapshot(out_dir: Path, include_run: Path | None = None) -> Path:
    repo_root = _repo_root()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    prompt_dir = repo_root / "paper_table_agent" / "prompts"
    _write_repo_tree(out_dir / "repo_tree.txt", repo_root)
    _write_db_schema(out_dir / "db_schema.sql", repo_root / "paper_table_agent" / "store" / "schema.sql")
    _copy_prompt_templates(prompt_dir, out_dir / "prompt_templates")
    _write_test_inventory(out_dir / "test_inventory.md", repo_root / "tests")
    _write_sanity_checks(out_dir / "sanity_checks.md")

    included_run_dir = None
    if include_run is not None:
        included_run_dir = out_dir / "included_run"
        _include_run_artifacts(Path(include_run), included_run_dir)

    project_state_md = _build_project_state_md(repo_root)
    (out_dir / "PROJECT_STATE.md").write_text(project_state_md, encoding="utf-8")
    project_state_json = _build_project_state_json(repo_root)
    (out_dir / "PROJECT_STATE.json").write_text(
        json.dumps(project_state_json, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    bundle_path = _write_snapshot_bundle(out_dir)
    if included_run_dir and not included_run_dir.exists():
        included_run_dir.mkdir(parents=True, exist_ok=True)
    return bundle_path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _write_repo_tree(out_path: Path, repo_root: Path) -> None:
    ignore_dirs = {".venv", "runs", "__pycache__"}
    lines: list[str] = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        rel_dir = Path(dirpath).relative_to(repo_root)
        dirnames[:] = [d for d in dirnames if d not in ignore_dirs]
        dirnames.sort()
        filenames.sort()
        for dirname in dirnames:
            rel_path = (rel_dir / dirname).as_posix()
            lines.append(f"{rel_path}/")
        for filename in filenames:
            rel_path = (rel_dir / filename).as_posix()
            lines.append(rel_path)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def _write_db_schema(out_path: Path, schema_path: Path) -> None:
    out_path.write_text(schema_path.read_text(encoding="utf-8"), encoding="utf-8")


def _copy_prompt_templates(prompt_dir: Path, output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    if not prompt_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
        return
    shutil.copytree(prompt_dir, output_dir)


def _write_test_inventory(out_path: Path, tests_dir: Path) -> None:
    lines = ["# Test inventory", ""]
    for test_file in sorted(tests_dir.glob("test_*.py")):
        functions = _extract_test_functions(test_file)
        lines.append(f"## {test_file.relative_to(_repo_root()).as_posix()}")
        if not functions:
            lines.append("- (no test functions found)")
        for name, doc in functions:
            detail = doc or name.replace("test_", "").replace("_", " ")
            lines.append(f"- `{name}`: {detail}")
        lines.append("")
    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _extract_test_functions(path: Path) -> list[tuple[str, str | None]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    results: list[tuple[str, str | None]] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            results.append((node.name, ast.get_docstring(node)))
    return results


def _write_sanity_checks(out_path: Path) -> None:
    content = textwrap.dedent(
        """
        # Sanity checks

        - `paper_table_agent/graph/runner.py::_run_health_checks`: probes model endpoint availability, runs a
          small `query_expand.md` completion, and validates embedding/reranker backends. Logs health_check events
          and applies fallbacks if needed.
        - `paper_table_agent/graph/reporting.py::_run_sanity_check`: fails the run report if matched PDFs exist
          but zero proposals were stored; captures diagnostics like schema column count, missing cell count,
          extraction invocation count, and evidence validation drops.
        """
    ).strip()
    out_path.write_text(content + "\n", encoding="utf-8")


def _include_run_artifacts(run_dir: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    allowed_files = [
        run_dir / "run_report.json",
        run_dir / "logs" / "run.log",
        run_dir / "exports" / "pdf_row_matches.csv",
        run_dir / "exports" / "mapping_report.html",
    ]
    for path in allowed_files:
        if path.exists() and path.is_file():
            target = out_dir / path.name
            shutil.copy2(path, target)

    db_path = run_dir / "proposals.sqlite"
    if db_path.exists():
        schema_out = out_dir / "db_schema.sql"
        _write_sqlite_schema(db_path, schema_out)


def _write_sqlite_schema(db_path: Path, out_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' ORDER BY name;").fetchall()
        statements = [row[0] for row in rows if row[0]]
    finally:
        conn.close()
    out_path.write_text("\n\n".join(statements) + "\n", encoding="utf-8")


def _build_project_state_md(repo_root: Path) -> str:
    prompt_index = _prompt_index()
    module_map = _module_map()
    config_overview = _config_overview()
    db_summary = _db_schema_summary(repo_root / "paper_table_agent" / "store" / "schema.sql")
    output_artifacts = _output_artifacts_summary()
    test_status = _testing_status(repo_root)
    todo_items = _load_open_tasks(repo_root / "specs" / "tasks.md")
    reproduce_commands = _reproduce_run_commands()

    prompt_lines = [
        f"- `{item['path']}` → `{item['schema']}` ({item['usage']})" for item in prompt_index
    ]
    module_lines = [f"- `{module.path}`: {module.purpose}" for module in module_map]

    todo_lines = [f"- {item}" for item in todo_items] if todo_items else ["- (none listed)"]

    return textwrap.dedent(
        f"""
        # Project Snapshot

        ## 1. What the app is
        Paper Table Agent is a local-first PDF → table proposal pipeline that reads a spreadsheet of papers and a
        folder of PDFs, matches each PDF to a row, and proposes values for missing cells with evidence. It keeps
        an audit trail of matches, retrieval hits, extraction proposals, and evidence highlights while avoiding
        overwriting existing data.

        The system is designed for batch processing with resumable runs, and stores its state in a local SQLite
        DB plus file-based artifacts under a run directory. The workflow is optimized for offline/LM-studio style
        inference but can also point at OpenAI-compatible backends.

        After a run completes, the Streamlit review UI lets you review only matched rows, approve or reject each
        proposal, and export a final spreadsheet plus audit logs. Evidence quotes and highlight metadata are
        surfaced alongside each proposed value.

        ## 2. Current repo entrypoints
        - CLI entrypoint: `paper_table_agent/cli.py` (commands: `ui`, `run`, `resume`, `stop`, `export`, `bundle`,
          `init-db`, `init-config`, `snapshot`).
        - Streamlit app entry: `paper_table_agent/ui/app.py` (`paper-table-agent ui`).
        - LangGraph initialization: `paper_table_agent/graph/workflow.py` (StateGraph + SqliteSaver checkpoints).

        ## 3. End-to-end data flow diagram
        ```text
        table load
          → schema parse
          → pdf parse
          → header/meta extract
          → matching
          → chunking/index
          → retrieval
          → extraction
          → evidence validation
          → persistence
          → review decisions
          → export
        ```

        ## 4. Key modules map (with paths)
        {chr(10).join(module_lines)}

        ## 5. Configuration overview
        {config_overview}

        ## 6. Database schema summary
        {db_summary}

        ## 7. Prompt templates index
        {chr(10).join(prompt_lines)}

        ## 8. Output artifacts
        {output_artifacts}

        ## 9. Testing status
        {test_status}

        ## 10. Known limitations / TODOs
        {chr(10).join(todo_lines)}

        ## 11. How to reproduce a run
        {reproduce_commands}
        """
    ).strip() + "\n"


def _build_project_state_json(repo_root: Path) -> dict[str, Any]:
    git_commit = _git_commit(repo_root)
    git_dirty = _git_dirty(repo_root)
    python_version = sys.version.replace("\n", " ")
    package_versions = _package_versions()
    important_files = _important_file_hashes(repo_root)
    config_schema = _config_schema()
    module_index = [module.__dict__ for module in _module_map()]
    return {
        "git_commit": git_commit,
        "git_dirty": git_dirty,
        "python_version": python_version,
        "package_versions": package_versions,
        "cli_version": __version__,
        "important_files": important_files,
        "run_config_schema": config_schema,
        "module_index": module_index,
    }


def _git_commit(repo_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return result.stdout.strip() or None


def _git_dirty(repo_root: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    return bool(result.stdout.strip())


def _package_versions() -> list[str]:
    packages = []
    for dist in metadata.distributions():
        name = dist.metadata.get("Name")
        version = dist.version
        if name and version:
            packages.append(f"{name}=={version}")
    return sorted(packages, key=str.lower)


def _important_file_hashes(repo_root: Path) -> list[dict[str, str]]:
    paths: list[Path] = []
    paths.extend((repo_root / "paper_table_agent").rglob("*") if (repo_root / "paper_table_agent").exists() else [])
    paths.extend((repo_root / "specs").rglob("*") if (repo_root / "specs").exists() else [])
    for filename in ["pyproject.toml", "README.md", "AGENTS.md"]:
        file_path = repo_root / filename
        if file_path.exists():
            paths.append(file_path)

    entries: list[dict[str, str]] = []
    for path in sorted({path for path in paths if path.is_file()}):
        entries.append(
            {
                "path": path.relative_to(repo_root).as_posix(),
                "sha256": _sha256(path),
            }
        )
    return entries


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _config_schema() -> dict[str, Any]:
    return _schema_for_model(RunConfig)


def _schema_for_model(model: type[BaseModel]) -> dict[str, Any]:
    schema: dict[str, Any] = {}
    for field_name, field in model.model_fields.items():
        annotation = field.annotation
        field_type = _format_type(annotation)
        if _is_base_model(annotation):
            schema[field_name] = _schema_for_model(annotation)
        else:
            schema[field_name] = field_type
    return schema


def _is_base_model(annotation: Any) -> bool:
    try:
        return issubclass(annotation, BaseModel)
    except TypeError:
        return False


def _format_type(annotation: Any) -> str:
    origin = get_origin(annotation)
    if origin is None:
        if annotation is None:
            return "None"
        if hasattr(annotation, "__name__"):
            return annotation.__name__
        return str(annotation)
    args = get_args(annotation)
    if origin in (list, tuple, set):
        inner = _format_type(args[0]) if args else "Any"
        return f"{origin.__name__}[{inner}]"
    if origin is dict:
        key_type = _format_type(args[0]) if args else "Any"
        value_type = _format_type(args[1]) if len(args) > 1 else "Any"
        return f"dict[{key_type}, {value_type}]"
    if origin is Iterable:
        inner = _format_type(args[0]) if args else "Any"
        return f"Iterable[{inner}]"
    if origin in {Union, UnionType}:
        return " | ".join(_format_type(arg) for arg in args)
    return " | ".join(_format_type(arg) for arg in args)


def _module_map() -> list[SnapshotModule]:
    return [
        SnapshotModule(
            path="paper_table_agent/graph/matching.py",
            purpose="Header extraction + match adjudication between PDFs and table rows.",
        ),
        SnapshotModule(
            path="paper_table_agent/pdf/parser.py",
            purpose="PDF parsing with text extraction and metadata handling.",
        ),
        SnapshotModule(
            path="paper_table_agent/pdf/ocr.py",
            purpose="OCR fallback for low-text PDFs.",
        ),
        SnapshotModule(
            path="paper_table_agent/retrieval/pipeline.py",
            purpose="Query expansion/HyDE and retrieval pipeline for evidence chunks.",
        ),
        SnapshotModule(
            path="paper_table_agent/graph/extraction.py",
            purpose="Group extraction, proposal verification, and evidence validation.",
        ),
        SnapshotModule(
            path="paper_table_agent/store/db.py",
            purpose="SQLite persistence for PDFs, matches, proposals, reviews, and events.",
        ),
        SnapshotModule(
            path="paper_table_agent/ui/app.py",
            purpose="Streamlit run + review UI.",
        ),
        SnapshotModule(
            path="paper_table_agent/graph/runner.py",
            purpose="Pipeline orchestration + health checks + report generation.",
        ),
    ]


def _prompt_index() -> list[dict[str, str]]:
    return [
        {
            "path": "paper_table_agent/prompts/match_header_extract.md",
            "schema": "HeaderExtractionResult",
            "usage": "paper_table_agent/graph/matching.py",
        },
        {
            "path": "paper_table_agent/prompts/match_adjudicate.md",
            "schema": "AdjudicationResult",
            "usage": "paper_table_agent/graph/matching.py",
        },
        {
            "path": "paper_table_agent/prompts/match_adjudicate_repair.md",
            "schema": "AdjudicationResult",
            "usage": "paper_table_agent/graph/matching.py",
        },
        {
            "path": "paper_table_agent/prompts/extract_group.md",
            "schema": "GroupExtractionResult",
            "usage": "paper_table_agent/graph/extraction.py",
        },
        {
            "path": "paper_table_agent/prompts/query_expand.md",
            "schema": "QueryExpansionResult",
            "usage": "paper_table_agent/retrieval/pipeline.py",
        },
        {
            "path": "paper_table_agent/prompts/hyde.md",
            "schema": "HydeResult",
            "usage": "paper_table_agent/retrieval/pipeline.py",
        },
        {
            "path": "paper_table_agent/prompts/verify_cell.md",
            "schema": "VerifyResult",
            "usage": "paper_table_agent/graph/extraction.py",
        },
        {
            "path": "paper_table_agent/prompts/verify_proposal.md",
            "schema": "ProposalVerificationResult",
            "usage": "paper_table_agent/graph/extraction.py",
        },
    ]


def _config_overview() -> str:
    provider = ProviderConfig()
    matching = MatchingConfig()
    extraction = ExtractionConfig()
    retrieval = RetrievalConfig()
    ocr = OcrConfig()
    grobid = GrobidConfig()
    output = OutputConfig()

    return textwrap.dedent(
        f"""
        `run_config.json` is the single source of truth for runs. The CLI requires a config path
        (`paper-table-agent run --config <path>`). The UI loads defaults from `run_config.json` in the repo
        root and overrides `table_path`/`pdf_folder` with the UI-selected values before launching a run.

        **Top-level fields**
        - `table_path` (required): input spreadsheet path.
        - `pdf_folder` (required): folder of PDFs.
        - `schema_sheet_name` (default: `{RunConfig.model_fields['schema_sheet_name'].default}`)
        - `schema_mode` (default: `{RunConfig.model_fields['schema_mode'].default}`), `schema_path` (optional)
        - `run_name` (optional), `title_col`, `authors_col`, `year_col` (optional)
        - `treat_single_space_as_empty` (default: {RunConfig.model_fields['treat_single_space_as_empty'].default})
        - `verify_mode` (default: {RunConfig.model_fields['verify_mode'].default})
        - `fast_mode` (default: {RunConfig.model_fields['fast_mode'].default})
        - `max_success_mode` (default: {RunConfig.model_fields['max_success_mode'].default})
        - `max_workers` (default: {RunConfig.model_fields['max_workers'].default})

        **Provider defaults**
        - `provider.mode`: `{provider.mode}`
        - `provider.base_url`: `{provider.base_url}`
        - `provider.model_header`/`model_match`/`model_extract`/`model_query_helper`: `{provider.model_header}`
        - `provider.max_prompt_chars`: {provider.max_prompt_chars}
        - `provider.mock_mode`: {provider.mock_mode}

        **Matching defaults**
        - `top_k`: {matching.top_k}, `confidence_threshold`: {matching.confidence_threshold},
          `confidence_margin`: {matching.confidence_margin}, `year_tolerance`: {matching.year_tolerance}

        **Extraction defaults**
        - `examples_per_col`: {extraction.examples_per_col}, `max_chunks`: {extraction.max_chunks},
          `retry_on_unclear`: {extraction.retry_on_unclear}, `retry_extra_chunks`: {extraction.retry_extra_chunks}

        **Retrieval defaults**
        - `top_k`: {retrieval.top_k}, `rerank_k`: {retrieval.rerank_k}, `max_context_chunks`: {retrieval.max_context_chunks}
        - `max_context_tokens`: {retrieval.max_context_tokens}, `query_variants`: {retrieval.query_variants}
        - `use_query_expansion`: {retrieval.use_query_expansion}, `use_hyde`: {retrieval.use_hyde}
        - `embedding_backend`: {retrieval.embedding_backend}, `reranker_backend`: {retrieval.reranker_backend}
        - `use_reranker`: {retrieval.use_reranker}

        **OCR defaults**
        - `enable_ocr`: {ocr.enable_ocr}, `ocr_trigger_min_chars_per_page`: {ocr.ocr_trigger_min_chars_per_page}

        **Grobid defaults**
        - `enable_grobid`: {grobid.enable_grobid}, `server_url`: {grobid.server_url}

        **Output defaults**
        - `debug_reports`: {output.debug_reports}
        """
    ).strip()


def _db_schema_summary(schema_path: Path) -> str:
    tables = _parse_schema_tables(schema_path)
    lines = []
    for table, columns in tables.items():
        important_cols = ", ".join(columns[:8]) if columns else ""
        lines.append(f"- `{table}`: {important_cols}")
    return "\n".join(lines)


def _parse_schema_tables(schema_path: Path) -> dict[str, list[str]]:
    tables: dict[str, list[str]] = {}
    current_table: str | None = None
    for line in schema_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("CREATE TABLE"):
            current_table = stripped.split()[4]
            tables[current_table] = []
            continue
        if current_table and stripped.startswith(")"):
            current_table = None
            continue
        if current_table and stripped:
            column = stripped.split()[0].strip("`\"")
            if column.lower() not in {"primary", "constraint"}:
                tables[current_table].append(column)
    return tables


def _output_artifacts_summary() -> str:
    return textwrap.dedent(
        """
        Runs live under `runs/<run_id>/` and include:
        - `run_config.json`: captured config + prompt versions + git commit.
        - `proposals.sqlite`: primary DB (matches, proposals, evidence, reviews, events).
        - `run_report.json`: summary metrics + sanity/health checks.
        - `logs/run.log`: run-time log output.
        - `checkpoints.sqlite`: LangGraph checkpoints for resumability.
        - `artifacts/parsed/`: parsed PDF text.
        - `artifacts/retrieval_indexes/`: retrieval indexes/chunks.
        - `artifacts/ocr/`: OCR outputs when enabled.
        - `artifacts/thumbnails/`: PDF thumbnails for UI review.
        - `exports/updated_table.xlsx`: exported table with decisions.
        - `exports/audit_log.csv`: decision log.
        - `exports/pdf_row_matches.csv`: debug-only row↔PDF match summary.
        - `exports/mapping_report.html`: debug-only HTML mapping report.
        """
    ).strip()


def _testing_status(repo_root: Path) -> str:
    return textwrap.dedent(
        f"""
        Tests are in `{(repo_root / 'tests').as_posix()}` and cover config validation, matching, retrieval,
        extraction, UI defaults, and an integration run using stub providers. Run them with:

        ```bash
        pytest
        ```

        Coverage gaps: none currently tracked in tasks.md.
        """
    ).strip()


def _load_open_tasks(tasks_path: Path) -> list[str]:
    if not tasks_path.exists():
        return []
    items = []
    for line in tasks_path.read_text(encoding="utf-8").splitlines():
        if "[ ]" in line:
            items.append(line.strip())
    return items


def _reproduce_run_commands() -> str:
    return textwrap.dedent(
        """
        ```bash
        paper-table-agent run --config run_config.json
        ```

        For offline testing, set `provider.mock_mode=true` or use the stub fixture config
        (`tests/fixtures/stub_run_config.json`).
        """
    ).strip()


def _write_snapshot_bundle(out_dir: Path) -> Path:
    bundle_path = out_dir / "snapshot_bundle.zip"
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in out_dir.rglob("*"):
            if path == bundle_path or path.is_dir():
                continue
            bundle.write(path, arcname=path.relative_to(out_dir))
    return bundle_path
