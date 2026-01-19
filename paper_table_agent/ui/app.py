from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
import httpx

from paper_table_agent.config import RunConfig, RunPaths, capture_run_config, create_run_paths, load_prompt_versions
from paper_table_agent.graph.exporter import export_run
from paper_table_agent.graph.workflow import run_workflow
from paper_table_agent.io.schema import group_columns, load_schema
from paper_table_agent.io.xlsx import load_table
from paper_table_agent.llm.embeddings import EmbeddingClient, EmbeddingConfig
from paper_table_agent.pdf.highlight import locate_quote, render_page_image
from paper_table_agent.retrieval.index import load_index
from paper_table_agent.retrieval.pipeline import RetrievalConfig, retrieve_context
from paper_table_agent.store.db import Store
from paper_table_agent.ui.registry import discover_pdf_folders, discover_runs, discover_tables

try:
    import tkinter as tk
    from tkinter import filedialog
except Exception:  # noqa: BLE001
    tk = None
    filedialog = None

st.set_page_config(page_title="Paper Table Agent", layout="wide")

DEFAULT_CONFIG_PATH = Path("run_config.json")
UPLOADS_DIR = Path("uploads")


st.title("Paper Table Agent")


run_tab, review_tab, advanced_tab, settings_tab, help_tab = st.tabs(
    ["Run", "Review", "Advanced", "Settings", "Help"]
)


def _load_default_config() -> dict[str, Any]:
    if not DEFAULT_CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        st.warning("Default run_config.json exists but could not be parsed.")
        return {}


def _refresh_registry(defaults: dict[str, Any] | None = None) -> None:
    st.session_state["runs"] = discover_runs()

    base_root = Path(".")
    default_table = None
    default_pdf = None
    if defaults:
        table_value = defaults.get("table_path")
        pdf_value = defaults.get("pdf_folder")
        if table_value:
            default_table = Path(table_value)
        if pdf_value:
            default_pdf = Path(pdf_value)

    table_roots = {base_root}
    if default_table and default_table.exists():
        table_roots.add(default_table.parent)

    pdf_roots = {base_root}
    if default_pdf and default_pdf.exists():
        pdf_roots.add(default_pdf)

    tables: set[Path] = set()
    for root in table_roots:
        tables.update(discover_tables(root))

    pdf_folders: set[Path] = set()
    for root in pdf_roots:
        pdf_folders.update(discover_pdf_folders(root))

    st.session_state["tables"] = sorted(tables)
    st.session_state["pdf_folders"] = sorted(pdf_folders)


def _choose_file(file_types: list[tuple[str, str]]) -> Path | None:
    if tk is None or filedialog is None:
        st.warning("File dialog is not available in this environment.")
        return None
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askopenfilename(filetypes=file_types)
    finally:
        root.destroy()
    return Path(selected) if selected else None


def _choose_folder() -> Path | None:
    if tk is None or filedialog is None:
        st.warning("Folder dialog is not available in this environment.")
        return None
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askdirectory()
    finally:
        root.destroy()
    return Path(selected) if selected else None


def _pick_table_path() -> None:
    selected = _choose_file([
        ("Tables", "*.xlsx *.csv"),
        ("All files", "*.*"),
    ])
    if selected:
        st.session_state["manual_table_path"] = str(selected)


def _pick_schema_path() -> None:
    selected = _choose_file([
        ("Schema", "*.xlsx"),
        ("All files", "*.*"),
    ])
    if selected:
        st.session_state["manual_schema_path"] = str(selected)


def _pick_pdf_folder() -> None:
    selected = _choose_folder()
    if selected:
        st.session_state["manual_pdf_folder"] = str(selected)


def _use_known_table(selected: str) -> None:
    st.session_state["manual_table_path"] = selected


def _use_known_pdf_folder(selected: str) -> None:
    st.session_state["manual_pdf_folder"] = selected


def _persist_upload(upload: Any, folder: Path) -> Path | None:
    if not upload:
        return None
    folder.mkdir(parents=True, exist_ok=True)
    safe_name = Path(upload.name).name
    target = folder / safe_name
    target.write_bytes(upload.getbuffer())
    return target


def _fetch_available_models(base_url: str, api_key: str | None) -> tuple[list[str], str | None]:
    url = f"{base_url.rstrip('/')}/models"
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        response = httpx.get(url, headers=headers, timeout=10.0)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:  # noqa: BLE001
        return [], f"Failed to load models: {exc}"
    models = sorted({item.get("id") for item in payload.get("data", []) if item.get("id")})
    return models, None


def _refresh_model_registry() -> None:
    settings = st.session_state.get("settings", {})
    models, error = _fetch_available_models(settings.get("base_url", ""), settings.get("api_key"))
    st.session_state["available_models"] = models
    st.session_state["model_registry_error"] = error
    st.session_state["model_registry_loaded"] = True


def _select_model(
    label: str,
    current: str | None,
    available: list[str],
    help_text: str | None = None,
    key: str | None = None,
) -> str:
    if available:
        if current and current in available:
            index = available.index(current)
        else:
            index = 0
            if current:
                st.warning(f"{label} '{current}' not found in LM Studio model list.")
        return st.selectbox(label, available, index=index, help=help_text, key=key)
    return st.text_input(label, value=current or "", help=help_text, key=key)


def _build_embedding_client(
    base_url: str,
    api_key: str | None,
    backend: str,
    model: str | None,
) -> EmbeddingClient | None:
    if backend == "tfidf":
        return None
    if backend != "lmstudio":
        return None
    if not model:
        return None
    return EmbeddingClient(
        EmbeddingConfig(
            base_url=base_url,
            api_key=api_key,
            model=model,
        )
    )


def _normalize_column_name(value: object) -> str:
    return str(value).replace("\u00a0", " ").strip()


def _build_column_map(columns: list[object]) -> dict[str, object]:
    mapping: dict[str, object] = {}
    for col in columns:
        normalized = _normalize_column_name(col)
        if normalized and normalized not in mapping:
            mapping[normalized] = col
    return mapping


def _format_time(value: float | None) -> str:
    if not value:
        return "Unknown"
    return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M")


def _render_validation_item(label: str, ok: bool, message: str | None = None) -> None:
    status = "✅" if ok else "⚠️"
    note = message or ("Ready" if ok else "Missing")
    st.markdown(f"{status} **{label}** — {note}")


def _apply_retrieval_preset(preset: str, config: RunConfig) -> None:
    if preset == "Fast":
        config.fast_mode = True
        config.retrieval.top_k = min(8, config.retrieval.top_k)
        config.retrieval.rerank_k = min(8, config.retrieval.rerank_k)
        config.retrieval.max_context_chunks = min(10, config.retrieval.max_context_chunks)
        config.retrieval.max_context_tokens = min(1200, config.retrieval.max_context_tokens)
        config.retrieval.query_variants = 0
        config.retrieval.use_query_expansion = False
        config.retrieval.use_hyde = False
        return
    config.fast_mode = False
    if preset == "Thorough":
        config.retrieval.top_k = max(16, config.retrieval.top_k)
        config.retrieval.rerank_k = max(16, config.retrieval.rerank_k)
        config.retrieval.max_context_chunks = max(20, config.retrieval.max_context_chunks)
        config.retrieval.query_variants = max(6, config.retrieval.query_variants)


def _run_summary(store: Store) -> dict[str, Any]:
    matches = [dict(row) for row in store.fetch_matches()]
    proposals = list(store.conn.execute("SELECT status, flags_json FROM proposals"))
    summary = {
        "matched": sum(1 for row in matches if row.get("status") == "matched"),
        "ambiguous": sum(1 for row in matches if row.get("status") == "ambiguous"),
        "unmatched": sum(1 for row in matches if row.get("status") in {"unmatched", "duplicate"}),
        "proposals": len(proposals),
        "needs_more_evidence": 0,
    }
    for row in proposals:
        flags = json.loads(row["flags_json"] or "{}")
        if flags.get("needs_more_evidence"):
            summary["needs_more_evidence"] += 1
    return summary


def _run_duration(run_dir: Path) -> str:
    config_path = run_dir / "run_config.json"
    start = config_path.stat().st_mtime if config_path.exists() else None
    completed_path = run_dir / "COMPLETED"
    end = completed_path.stat().st_mtime if completed_path.exists() else None
    if not start or not end:
        return "Unknown"
    seconds = max(0, int(end - start))
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _get_row_completion(total: int, decided: int) -> str:
    if total == 0:
        return "0%"
    return f"{int((decided / total) * 100)}%"


def _proposal_state(proposal: dict[str, Any], review: dict[str, Any] | None) -> str:
    if review:
        return review.get("decision", "reviewed")
    flags = proposal.get("flags", {})
    if flags.get("needs_more_evidence"):
        return "needs_more_evidence"
    status = proposal.get("status") or "proposed"
    if status in {"found", "inferred", "verify"}:
        return "proposed"
    if status in {"unclear", "no_evidence", "not_found", "error"}:
        return "unclear"
    return status


def _evidence_label(evidence: dict[str, Any]) -> str:
    quote = (evidence.get("quote") or "").strip()
    snippet = quote[:120] + ("…" if len(quote) > 120 else "")
    return f"Page {evidence.get('page')}: {snippet}".strip()


def _key_columns(specs: list[Any]) -> list[str]:
    keys: list[str] = []
    for spec in specs:
        priority = (spec.priority or "").strip().lower()
        if priority in {"key", "primary", "high"}:
            keys.append(spec.column_name)
    return keys


def _resolve_schema_source(schema_mode: str, table_path: Path, schema_path: Path | None) -> Path:
    if schema_mode == "separate" and schema_path:
        return schema_path
    return table_path


if "default_config" not in st.session_state:
    st.session_state["default_config"] = _load_default_config()

if "runs" not in st.session_state:
    _refresh_registry(st.session_state.get("default_config"))

if "selected_run_dir" not in st.session_state:
    st.session_state["selected_run_dir"] = None

if "review_auto_advance" not in st.session_state:
    st.session_state["review_auto_advance"] = True

if "settings" not in st.session_state:
    defaults = st.session_state.get("default_config", {})
    provider_defaults = defaults.get("provider", {})
    retrieval_defaults = defaults.get("retrieval", {})
    st.session_state["settings"] = {
        "provider_type": "LM Studio",
        "base_url": provider_defaults.get("base_url", "http://localhost:1234/v1"),
        "api_key": provider_defaults.get("api_key"),
        "model_header": provider_defaults.get("model_header", "gpt-oss-20b"),
        "model_match": provider_defaults.get("model_match", "gpt-oss-20b"),
        "model_extract": provider_defaults.get("model_extract", "gpt-oss-20b"),
        "model_query_helper": provider_defaults.get("model_query_helper", "gpt-oss-20b"),
        "embedding_backend": retrieval_defaults.get("embedding_backend", "tfidf"),
        "embedding_model": retrieval_defaults.get("embedding_model"),
        "reranker_backend": retrieval_defaults.get("reranker_backend", "tfidf"),
        "reranker_model": retrieval_defaults.get("reranker_model"),
        "use_reranker": retrieval_defaults.get("use_reranker", True),
        "max_workers": defaults.get("max_workers", 1),
        "retry_on_unclear": defaults.get("extraction", {}).get("retry_on_unclear", True),
        "retry_extra_chunks": defaults.get("extraction", {}).get("retry_extra_chunks", 6),
    }


runs = st.session_state.get("runs", [])
selected_run_info = None
selected_run_dir = st.session_state.get("selected_run_dir")
if selected_run_dir:
    selected_run_info = next((run for run in runs if run.run_dir == selected_run_dir), None)

with st.container():
    header_left, header_mid, header_right = st.columns([2, 2, 1])
    with header_left:
        st.markdown("**Paper Table Agent**")
    with header_mid:
        label = selected_run_info.label if selected_run_info else "No run selected"
        st.caption(f"Selected run: {label}")
    with header_right:
        status_label = selected_run_info.status if selected_run_info else "idle"
        st.markdown(f"**Status:** `{status_label}`")


with settings_tab:
    st.header("Settings")
    settings = st.session_state["settings"]
    provider_type = st.selectbox("Provider", ["LM Studio", "Ollama", "OpenAI-compatible"], index=0)
    settings["provider_type"] = provider_type
    settings["base_url"] = st.text_input("Base URL", value=settings["base_url"])
    settings["api_key"] = st.text_input("API key", value=settings["api_key"] or "", type="password")

    st.subheader("Model routing")
    available_models = st.session_state.get("available_models", [])
    if provider_type == "LM Studio" and not st.session_state.get("model_registry_loaded"):
        _refresh_model_registry()
        available_models = st.session_state.get("available_models", [])
    if provider_type == "LM Studio":
        if st.button("Refresh model list"):
            _refresh_model_registry()
            available_models = st.session_state.get("available_models", [])
        registry_error = st.session_state.get("model_registry_error")
        if registry_error:
            st.warning(registry_error)
        elif available_models:
            st.caption(f"{len(available_models)} models available from LM Studio.")
        else:
            st.info("No LM Studio models detected yet. Refresh once LM Studio is running.")

    fallback_models = [
        settings["model_header"],
        settings["model_match"],
        settings["model_extract"],
        settings["model_query_helper"],
        "gpt-oss-20b",
        "gpt-4o-mini",
    ]
    fallback_models = sorted({option for option in fallback_models if option})
    model_options = available_models if provider_type == "LM Studio" else fallback_models

    settings["model_header"] = _select_model("Header extraction model", settings["model_header"], model_options)
    settings["model_match"] = _select_model("Match adjudication model", settings["model_match"], model_options)
    settings["model_extract"] = _select_model("Extraction model", settings["model_extract"], model_options)
    settings["model_query_helper"] = _select_model("Query expansion model", settings["model_query_helper"], model_options)

    backend_options = ["tfidf", "lmstudio"]
    if settings["embedding_backend"] not in backend_options:
        st.warning(f"Unsupported embedding backend '{settings['embedding_backend']}' reset to tfidf.")
        settings["embedding_backend"] = "tfidf"
    if settings["reranker_backend"] not in backend_options:
        st.warning(f"Unsupported reranker backend '{settings['reranker_backend']}' reset to tfidf.")
        settings["reranker_backend"] = "tfidf"
    embed_index = backend_options.index(settings["embedding_backend"]) if settings["embedding_backend"] in backend_options else 0
    rerank_index = backend_options.index(settings["reranker_backend"]) if settings["reranker_backend"] in backend_options else 0
    settings["embedding_backend"] = st.selectbox("Embedding backend", backend_options, index=embed_index)
    if settings["embedding_backend"] == "lmstudio":
        settings["embedding_model"] = _select_model(
            "Embedding model",
            settings.get("embedding_model"),
            available_models,
            help_text="Select a model that supports embeddings in LM Studio.",
        )
    else:
        settings["embedding_model"] = None

    settings["reranker_backend"] = st.selectbox("Reranker backend", backend_options, index=rerank_index)
    if settings["reranker_backend"] == "lmstudio":
        settings["reranker_model"] = _select_model(
            "Reranker model",
            settings.get("reranker_model"),
            available_models,
            help_text="Select a model to compute rerank embeddings.",
        )
    else:
        settings["reranker_model"] = None
    settings["use_reranker"] = st.checkbox("Use reranker", value=bool(settings["use_reranker"]))

    st.subheader("Performance controls")
    settings["max_workers"] = st.number_input("Concurrency (PDFs in parallel)", min_value=1, max_value=8,
                                               value=int(settings["max_workers"]))
    settings["retry_on_unclear"] = st.checkbox("Retry unclear proposals", value=bool(settings["retry_on_unclear"]))
    settings["retry_extra_chunks"] = st.number_input(
        "Retry extra chunks",
        min_value=0,
        max_value=20,
        value=int(settings["retry_extra_chunks"]),
    )

    st.caption("Caching of parsed pages and retrieval indexes is enabled by default.")


with run_tab:
    st.header("Run")
    if st.button("Refresh registry"):
        _refresh_registry(st.session_state.get("default_config"))

    runs = st.session_state.get("runs", [])
    tables = st.session_state.get("tables", [])
    pdf_folders = st.session_state.get("pdf_folders", [])

    default_config = st.session_state.get("default_config", {})
    default_table_path = Path(default_config["table_path"]) if default_config.get("table_path") else None
    default_pdf_folder = Path(default_config["pdf_folder"]) if default_config.get("pdf_folder") else None

    config_panel, exec_panel = st.columns([1.1, 1.9])

    with config_panel:
        st.subheader("Run configuration")
        if "manual_table_path" not in st.session_state:
            st.session_state["manual_table_path"] = str(default_table_path) if default_table_path else ""

        col_table_path, col_table_browse = st.columns([4, 1])
        with col_table_path:
            st.text_input("Table path", key="manual_table_path")
        with col_table_browse:
            st.button("Browse", key="browse-table", on_click=_pick_table_path)

        manual_table_path = st.session_state.get("manual_table_path", "").strip()
        table_path = Path(manual_table_path) if manual_table_path else None

        if tables:
            known_table = st.selectbox(
                "Known tables",
                options=[str(path) for path in tables],
            )
            st.button(
                "Use selected table",
                on_click=_use_known_table,
                args=(known_table,),
            )

        if table_path and table_path.exists():
            st.caption(f"Selected: {table_path.name} (last modified {_format_time(table_path.stat().st_mtime)})")

        st.markdown("**PDF folder**")
        if "manual_pdf_folder" not in st.session_state:
            st.session_state["manual_pdf_folder"] = str(default_pdf_folder) if default_pdf_folder else ""
        col_pdf_path, col_pdf_browse = st.columns([4, 1])
        with col_pdf_path:
            st.text_input("PDF folder path", key="manual_pdf_folder")
        with col_pdf_browse:
            st.button("Browse", key="browse-pdf-folder", on_click=_pick_pdf_folder)

        if pdf_folders:
            known_pdf = st.selectbox(
                "Known PDF folders",
                options=[str(path) for path in pdf_folders],
            )
            st.button(
                "Use selected PDF folder",
                on_click=_use_known_pdf_folder,
                args=(known_pdf,),
            )
        manual_pdf_folder = st.session_state.get("manual_pdf_folder", "").strip()
        pdf_folder = Path(manual_pdf_folder) if manual_pdf_folder else None

        st.markdown("**Schema source**")
        schema_options = ["Use schema sheet from XLSX", "Select separate schema XLSX"]
        default_schema_index = 0
        if table_path and table_path.suffix.lower() != ".xlsx":
            default_schema_index = 1
        schema_source = st.selectbox(
            "Schema source",
            schema_options,
            index=default_schema_index,
        )
        schema_mode = "sheet" if schema_source == "Use schema sheet from XLSX" else "separate"

        schema_sheet = default_config.get("schema_sheet_name", "schema")
        schema_path = None
        if schema_mode == "separate":
            schema_upload = st.file_uploader("Schema XLSX", type=["xlsx"], key="schema-upload")
            uploaded_schema_path = _persist_upload(schema_upload, UPLOADS_DIR / "schemas")
            if "manual_schema_path" not in st.session_state:
                st.session_state["manual_schema_path"] = ""
            if uploaded_schema_path:
                st.session_state["manual_schema_path"] = str(uploaded_schema_path)
            col_schema_path, col_schema_browse = st.columns([4, 1])
            with col_schema_path:
                st.text_input("Schema path", key="manual_schema_path")
            with col_schema_browse:
                st.button("Browse", key="browse-schema", on_click=_pick_schema_path)
            manual_schema_path = st.session_state.get("manual_schema_path", "").strip()
            schema_path = Path(manual_schema_path) if manual_schema_path else None

        schema_source_path = None
        if table_path and schema_mode == "sheet":
            schema_source_path = table_path
        elif schema_mode == "separate":
            schema_source_path = schema_path

        if schema_mode == "sheet" and table_path and table_path.suffix.lower() != ".xlsx":
            st.warning("CSV tables require a separate schema XLSX.")
        if schema_source_path and schema_source_path.exists() and schema_source_path.suffix.lower() == ".xlsx":
            try:
                sheet_names = pd.ExcelFile(schema_source_path).sheet_names
                if schema_sheet in sheet_names:
                    schema_index = sheet_names.index(schema_sheet)
                else:
                    schema_index = 0
                schema_sheet = st.selectbox("Schema sheet", options=sheet_names, index=schema_index)
            except Exception as exc:  # noqa: BLE001
                st.error(f"Failed to read workbook sheets: {exc}")
        elif schema_mode == "sheet":
            st.caption("Schema sheet defaults to 'schema' for CSV inputs.")

        st.markdown("**Run name**")
        if "run_name" not in st.session_state:
            fallback = table_path.stem if table_path else "new-run"
            st.session_state["run_name"] = f"{fallback}-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
        st.text_input("Run name", key="run_name")

        st.markdown("**Mode**")
        run_mode = st.radio("Run mode", ["Propose", "Verify-only"], horizontal=True)

        st.caption("Locked cells are non-empty values (except a single space).")

        st.markdown("**Models**")
        settings = st.session_state["settings"]
        available_models = st.session_state.get("available_models", [])
        fallback_models = [settings["model_extract"], settings["model_header"], settings["model_match"]]
        if settings.get("provider_type") == "LM Studio" and available_models:
            model_options = available_models
        else:
            model_options = sorted({option for option in fallback_models if option})
        extraction_model = _select_model("LLM for extraction", settings["model_extract"], model_options)

        backend_options = ["tfidf", "lmstudio"]
        embed_index = backend_options.index(settings["embedding_backend"]) if settings["embedding_backend"] in backend_options else 0
        rerank_index = backend_options.index(settings["reranker_backend"]) if settings["reranker_backend"] in backend_options else 0
        embedding_backend = st.selectbox(
            "Embedding backend",
            backend_options,
            index=embed_index,
            key="run-embedding-backend",
        )
        embedding_model = None
        if embedding_backend == "lmstudio":
            embedding_model = _select_model(
                "Embedding model",
                settings.get("embedding_model"),
                available_models,
                key="run-embedding-model",
            )

        reranker_backend = st.selectbox(
            "Reranker backend",
            backend_options,
            index=rerank_index,
            key="run-reranker-backend",
        )
        reranker_model = None
        if reranker_backend == "lmstudio":
            reranker_model = _select_model(
                "Reranker model",
                settings.get("reranker_model"),
                available_models,
                key="run-reranker-model",
            )

        st.markdown("**Retrieval strength**")
        retrieval_preset = st.radio("Preset", ["Fast", "Balanced", "Thorough"], horizontal=True)

        st.markdown("**OCR fallback**")
        ocr_enabled = st.checkbox("Enable OCR fallback", value=False)

        st.markdown("**GROBID**")
        grobid_enabled = st.checkbox("Enable GROBID", value=False)
        grobid_url = None
        if grobid_enabled:
            grobid_url = st.text_input("GROBID server URL", value="http://localhost:8070")

        st.divider()
        st.markdown("**Schema groups**")
        if st.button("Load schema"):
            if schema_source_path and schema_sheet:
                try:
                    source_path = _resolve_schema_source(
                        schema_mode,
                        table_path or schema_source_path,
                        schema_path,
                    )
                    schema_specs = load_schema(source_path, schema_sheet)
                    grouped = group_columns(schema_specs)
                    st.session_state["group_mapping"] = {
                        name: [spec.column_name for spec in specs] for name, specs in grouped.items()
                    }
                    if not st.session_state.get("group_selection"):
                        st.session_state["group_selection"] = list(st.session_state["group_mapping"].keys())
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Failed to load schema: {exc}")
        if st.session_state.get("group_mapping"):
            st.session_state["group_selection"] = st.multiselect(
                "Groups to extract (order matters)",
                list(st.session_state["group_mapping"].keys()),
                default=st.session_state.get("group_selection", []),
            )

        st.markdown("**Validation**")
        valid_table = bool(table_path and table_path.exists())
        valid_pdf = bool(pdf_folder and pdf_folder.exists())
        valid_schema = bool(schema_source_path and schema_source_path.exists())
        if schema_mode == "sheet" and table_path and table_path.suffix.lower() != ".xlsx":
            valid_schema = False
        valid_embedding = embedding_backend != "lmstudio" or bool(embedding_model)
        valid_reranker = True
        if settings["use_reranker"]:
            valid_reranker = reranker_backend != "lmstudio" or bool(reranker_model)
        _render_validation_item("Table", valid_table)
        _render_validation_item("PDF folder", valid_pdf)
        _render_validation_item("Schema", valid_schema)
        _render_validation_item("Embedding model", valid_embedding, "Select a model" if not valid_embedding else None)
        if settings["use_reranker"]:
            _render_validation_item("Reranker model", valid_reranker, "Select a model" if not valid_reranker else None)
        run_ready = valid_table and valid_pdf and valid_schema and valid_embedding and valid_reranker

        if st.button("Start run", disabled=not run_ready):
            if not run_ready:
                st.error("Select a valid table, schema, and PDF folder before starting a run.")
            else:
                config = RunConfig(
                    table_path=Path(table_path),
                    pdf_folder=Path(pdf_folder),
                    schema_sheet_name=schema_sheet,
                    schema_mode=schema_mode,
                    schema_path=schema_path if schema_mode == "separate" else None,
                    run_name=st.session_state.get("run_name"),
                    verify_mode=run_mode == "Verify-only",
                )
                config.provider.base_url = settings["base_url"]
                config.provider.api_key = settings["api_key"] or None
                config.provider.model_header = settings["model_header"]
                config.provider.model_match = settings["model_match"]
                config.provider.model_extract = extraction_model
                config.provider.model_query_helper = settings["model_query_helper"]
                config.retrieval.embedding_backend = embedding_backend
                config.retrieval.embedding_model = embedding_model
                config.retrieval.reranker_backend = reranker_backend
                config.retrieval.reranker_model = reranker_model
                config.retrieval.use_reranker = settings["use_reranker"]
                config.ocr.enable_ocr = ocr_enabled
                config.grobid.enable_grobid = grobid_enabled
                if grobid_url:
                    config.grobid.server_url = grobid_url
                config.max_workers = int(settings["max_workers"])
                config.extraction.retry_on_unclear = bool(settings["retry_on_unclear"])
                config.extraction.retry_extra_chunks = int(settings["retry_extra_chunks"])
                _apply_retrieval_preset(retrieval_preset, config)

                if "group_mapping" not in st.session_state:
                    st.session_state["group_mapping"] = {}
                if "group_selection" not in st.session_state:
                    st.session_state["group_selection"] = []

                if table_path and schema_sheet:
                    try:
                        schema_specs = load_schema(_resolve_schema_source(schema_mode, table_path, schema_path), schema_sheet)
                        grouped = group_columns(schema_specs)
                        st.session_state["group_mapping"] = {
                            name: [spec.column_name for spec in specs] for name, specs in grouped.items()
                        }
                        if not st.session_state["group_selection"]:
                            st.session_state["group_selection"] = list(st.session_state["group_mapping"].keys())
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Failed to load schema: {exc}")

                if st.session_state.get("group_selection") and st.session_state.get("group_mapping"):
                    config.extraction.groups = [
                        {"name": group, "columns": st.session_state["group_mapping"][group]}
                        for group in st.session_state["group_selection"]
                    ]

                run_paths = create_run_paths(config.table_path, run_name=config.run_name)
                prompt_versions = load_prompt_versions(Path("paper_table_agent/prompts"))
                capture_run_config(config, run_paths, prompt_versions)
                store = Store.init_db(run_paths.db_path)
                run_workflow(config=config, run_paths=run_paths, store=store)
                st.session_state["selected_run_dir"] = run_paths.run_dir
                _refresh_registry()
                st.success(f"Run completed: {run_paths.run_dir}")

    with exec_panel:
        st.subheader("Run execution")
        if not runs:
            st.info("Start a run to see execution status, logs, and controls.")
        else:
            st.caption("Progress updates appear after each PDF is processed.")
            st.progress(0, text="Waiting to start")
            st.write("Current step: idle")
            st.write("Current PDF: —")

            run_options = {run.label: run for run in runs}
            resume_label = (
                st.selectbox("Select run", options=list(run_options.keys()), key="resume-run")
                if run_options
                else None
            )
            selected_run = run_options.get(resume_label) if resume_label else None

            with st.expander("Live logs", expanded=False):
                st.caption("Filters: errors | warnings | info")
                show_errors = st.checkbox("Errors", value=True, key="log-errors")
                show_warnings = st.checkbox("Warnings", value=True, key="log-warnings")
                show_info = st.checkbox("Info", value=True, key="log-info")
                if selected_run:
                    store = Store.init_db(selected_run.run_dir / "proposals.sqlite")
                    levels = []
                    if show_errors:
                        levels.append("error")
                    if show_warnings:
                        levels.append("warning")
                    if show_info:
                        levels.append("info")
                    if levels:
                        placeholders = ",".join("?" for _ in levels)
                        query = (
                            "SELECT level, event_type, payload_json, created_at "
                            f"FROM events WHERE level IN ({placeholders}) "
                            "ORDER BY created_at DESC LIMIT 30"
                        )
                        events = store.conn.execute(query, tuple(levels)).fetchall()
                        for event in events:
                            st.write(f"[{event['level']}] {event['event_type']} — {event['created_at']}")
                            st.code(event["payload_json"])
                    else:
                        st.info("Enable at least one log filter.")

            st.markdown("**Run actions**")
            action_col1, action_col2, action_col3 = st.columns(3)
            with action_col1:
                if st.button("Pause", disabled=not selected_run) and selected_run:
                    (selected_run.run_dir / "PAUSE").write_text("pause", encoding="utf-8")
                    _refresh_registry()
                    st.warning("Pause requested. The run will halt after the current PDF.")
            with action_col2:
                if st.button("Resume", disabled=not selected_run) and selected_run:
                    pause_path = selected_run.run_dir / "PAUSE"
                    if pause_path.exists():
                        pause_path.unlink()
                    config_path = selected_run.run_dir / "run_config.json"
                    config = RunConfig.model_validate_json(config_path.read_text(encoding="utf-8"))
                    store = Store.init_db(selected_run.run_dir / "proposals.sqlite")
                    run_workflow(config=config, run_paths=RunPaths(run_dir=selected_run.run_dir), store=store, resume=True)
                    st.session_state["selected_run_dir"] = selected_run.run_dir
                    _refresh_registry()
                    st.success(f"Resumed run: {selected_run.run_dir}")
            with action_col3:
                if st.button("Stop", disabled=not selected_run) and selected_run:
                    (selected_run.run_dir / "STOP").write_text("stop", encoding="utf-8")
                    _refresh_registry()
                    st.warning("Stop requested. The run will halt after the current PDF.")

            if selected_run:
                st.subheader("Completion summary")
                store = Store.init_db(selected_run.run_dir / "proposals.sqlite")
                summary = _run_summary(store)
                st.write(
                    {
                        "Matched PDFs": summary["matched"],
                        "Ambiguous": summary["ambiguous"],
                        "Unmatched": summary["unmatched"],
                        "Proposals": summary["proposals"],
                        "Needs more evidence": summary["needs_more_evidence"],
                        "Run duration": _run_duration(selected_run.run_dir),
                    }
                )
                st.markdown("**Artifacts**")
                st.text_input("Run artifacts path", value=str(selected_run.run_dir), disabled=True)
                if st.button("Go to Review"):
                    st.session_state["selected_run_dir"] = selected_run.run_dir
                    st.info("Switch to the Review tab to continue.")


with review_tab:
    st.header("Review")
    runs = [run for run in st.session_state.get("runs", []) if run.status == "completed"]
    if not runs:
        st.info("No completed runs yet.")
    else:
        run_labels = [run.label for run in runs]
        default_run_dir = st.session_state.get("selected_run_dir")
        default_index = 0
        if default_run_dir:
            for idx, run in enumerate(runs):
                if run.run_dir == default_run_dir:
                    default_index = idx
                    break
        selected_label = st.selectbox("Run", run_labels, index=default_index, key="review-run")
        selected_run = runs[run_labels.index(selected_label)]
        st.session_state["selected_run_dir"] = selected_run.run_dir

        store = Store.init_db(selected_run.run_dir / "proposals.sqlite")
        run_config = json.loads((selected_run.run_dir / "run_config.json").read_text(encoding="utf-8"))
        table = load_table(Path(run_config["table_path"]))
        column_map = _build_column_map(list(table.dataframe.columns))
        specs = load_schema(
            _resolve_schema_source(
                run_config.get("schema_mode", "sheet"),
                Path(run_config["table_path"]),
                Path(run_config["schema_path"]) if run_config.get("schema_path") else None,
            ),
            run_config["schema_sheet_name"],
        )
        key_columns = _key_columns(specs)
        pdf_rows = [dict(row) for row in store.list_pdfs()]
        pdf_map = {row["pdf_id"]: row["path"] for row in pdf_rows}
        pdf_meta = {row["pdf_id"]: row for row in pdf_rows}
        matches = [dict(row) for row in store.fetch_matches()]
        match_by_row: dict[str, list[dict[str, Any]]] = {}
        for match in matches:
            if match.get("row_id"):
                match_by_row.setdefault(match["row_id"], []).append(match)
        candidates = [dict(row) for row in store.fetch_match_candidates()]
        candidate_by_row: dict[str, list[dict[str, Any]]] = {}
        for candidate in candidates:
            if candidate.get("row_id"):
                candidate_by_row.setdefault(candidate["row_id"], []).append(candidate)
        pdf_options = ["All PDFs"] + list(pdf_map.keys())
        selected_pdf = st.selectbox("PDF", pdf_options, key="review-pdf")

        proposals_meta = [dict(row) for row in store.conn.execute(
            "SELECT proposal_id, row_id, pdf_id, column, status, confidence, proposed_value, flags_json "
            "FROM proposals"
        )]
        for proposal in proposals_meta:
            proposal["flags"] = json.loads(proposal.get("flags_json") or "{}")

        reviews = store.fetch_reviews()
        rows = [dict(row) for row in store.fetch_rows()]
        row_lookup = {row["row_id"]: row for row in rows}

        all_columns = sorted({spec.column_name for spec in specs})

        st.subheader("Filters")
        status_filter = st.multiselect(
            "Status",
            ["proposed", "unclear", "needs_more_evidence", "accepted", "rejected"],
            default=["proposed"],
        )
        confidence_min, confidence_max = st.slider("Confidence range", 0.0, 1.0, (0.0, 1.0))
        column_filter = st.multiselect("Columns", all_columns, default=[])
        search = st.text_input("Search", value="")

        search_row_ids: set[str] | None = None
        if search:
            search_term = f"%{search.lower()}%"
            if selected_pdf != "All PDFs":
                matches = store.conn.execute(
                    """
                    SELECT DISTINCT row_id
                    FROM proposals
                    WHERE pdf_id = ?
                      AND (
                        lower(column) LIKE ?
                        OR lower(proposed_value) LIKE ?
                        OR lower(evidence_json) LIKE ?
                      )
                    """,
                    (selected_pdf, search_term, search_term, search_term),
                )
            else:
                matches = store.conn.execute(
                    """
                    SELECT DISTINCT row_id
                    FROM proposals
                    WHERE lower(column) LIKE ?
                       OR lower(proposed_value) LIKE ?
                       OR lower(evidence_json) LIKE ?
                    """,
                    (search_term, search_term, search_term),
                )
            search_row_ids = {row["row_id"] for row in matches}

        filtered_row_ids: set[str] = set()
        row_stats: dict[str, dict[str, Any]] = {}
        row_totals: dict[str, dict[str, Any]] = {}
        for proposal in proposals_meta:
            if selected_pdf != "All PDFs" and proposal.get("pdf_id") != selected_pdf:
                continue
            row_total = row_totals.setdefault(proposal["row_id"], {"total": 0, "decided": 0})
            row_total["total"] += 1
            if reviews.get(proposal["proposal_id"]):
                row_total["decided"] += 1
            review = reviews.get(proposal["proposal_id"])
            state = _proposal_state(proposal, review)
            confidence = proposal.get("confidence") or 0.0
            if confidence < confidence_min or confidence > confidence_max:
                continue
            if column_filter and proposal.get("column") not in column_filter:
                continue
            if status_filter and state not in status_filter:
                continue
            if search_row_ids is not None and proposal["row_id"] not in search_row_ids:
                continue
            filtered_row_ids.add(proposal["row_id"])
            stats = row_stats.setdefault(proposal["row_id"], {
                "total": 0,
                "decided": 0,
                "proposed": 0,
                "needs_more_evidence": 0,
                "unclear": 0,
            })
            stats["total"] += 1
            if review:
                stats["decided"] += 1
            if state == "proposed":
                stats["proposed"] += 1
            if state == "needs_more_evidence":
                stats["needs_more_evidence"] += 1
            if state == "unclear":
                stats["unclear"] += 1

        overall_total = sum(total["total"] for total in row_totals.values())
        overall_decided = sum(total["decided"] for total in row_totals.values())
        st.caption(f"Run completion: {_get_row_completion(overall_total, overall_decided)} decided")

        filtered_rows = [row_lookup[row_id] for row_id in filtered_row_ids if row_id in row_lookup]
        filtered_rows.sort(
            key=lambda row: (
                -row_stats.get(row["row_id"], {}).get("proposed", 0),
                -row_stats.get(row["row_id"], {}).get("needs_more_evidence", 0),
                -row_stats.get(row["row_id"], {}).get("unclear", 0),
                row.get("row_index", 0),
            )
        )

        if not filtered_rows:
            st.info("No rows match the current filters.")
        else:
            row_labels = []
            for row in filtered_rows:
                totals = row_totals.get(row["row_id"], {})
                complete = totals.get("decided", 0) >= totals.get("total", 0) and totals.get("total", 0) > 0
                suffix = " ✅" if complete else ""
                row_labels.append(f"Row {row['row_index']} — {row.get('title', '')}{suffix}")
            if "selected_row_index" not in st.session_state:
                st.session_state["selected_row_index"] = 0
            if st.session_state["selected_row_index"] >= len(filtered_rows):
                st.session_state["selected_row_index"] = 0

            nav_col1, nav_col2, nav_col3, nav_col4 = st.columns([1, 1, 2, 1])
            with nav_col1:
                if st.button("Prev row"):
                    st.session_state["selected_row_index"] = max(0, st.session_state["selected_row_index"] - 1)
            with nav_col2:
                if st.button("Next row"):
                    st.session_state["selected_row_index"] = min(
                        len(filtered_rows) - 1, st.session_state["selected_row_index"] + 1
                    )
            with nav_col3:
                jump = st.number_input(
                    "Row index jump",
                    min_value=1,
                    max_value=len(filtered_rows),
                    value=st.session_state["selected_row_index"] + 1,
                )
                if st.button("Go"):
                    st.session_state["selected_row_index"] = int(jump - 1)
            with nav_col4:
                current_position = st.session_state["selected_row_index"] + 1
                st.caption(f"Row {current_position} of {len(filtered_rows)}")

            selection = st.selectbox(
                "Row",
                row_labels,
                index=st.session_state["selected_row_index"],
            )
            row_idx = row_labels.index(selection)
            st.session_state["selected_row_index"] = row_idx
            row_data = filtered_rows[row_idx]
            row_id = row_data["row_id"]

            row_proposals = [dict(row) for row in store.fetch_proposals_for_row(row_id)]
            for proposal in row_proposals:
                proposal["flags"] = json.loads(proposal.get("flags_json") or "{}")
                proposal["evidence"] = json.loads(proposal.get("evidence_json") or "[]")
            if selected_pdf != "All PDFs":
                row_proposals = [proposal for proposal in row_proposals if proposal.get("pdf_id") == selected_pdf]
            row_proposals.sort(key=lambda item: item.get("column", ""))

            if not row_proposals:
                st.info("No proposals for this row.")
            else:
                index_key = f"proposal-index-{row_id}"
                if index_key not in st.session_state:
                    st.session_state[index_key] = 0
                current_index = st.session_state[index_key]
                if current_index >= len(row_proposals):
                    current_index = 0
                current = row_proposals[current_index]

                left_col, right_col = st.columns([1.1, 1.4])
                with left_col:
                    st.subheader("Row context")
                    context_payload = {
                        "Title": row_data.get("title"),
                        "Authors": row_data.get("authors"),
                        "Year": row_data.get("year"),
                    }
                    for col in key_columns:
                        normalized = _normalize_column_name(col)
                        resolved = column_map.get(normalized)
                        if resolved is not None:
                            context_payload[col] = table.dataframe.loc[row_data["row_index"], resolved]
                    st.write(context_payload)
                    row_matches = match_by_row.get(row_id, [])
                    if row_matches:
                        st.markdown("**Mapping status**")
                        for match in row_matches:
                            st.write(
                                {
                                    "PDF": match.get("pdf_id"),
                                    "Status": match.get("status"),
                                    "Confidence": match.get("confidence"),
                                    "PDF path": pdf_map.get(match.get("pdf_id")),
                                }
                            )
                        if any(match.get("status") == "ambiguous" for match in row_matches):
                            st.markdown("**Top candidates**")
                            for candidate in candidate_by_row.get(row_id, [])[:5]:
                                st.write(
                                    {
                                        "Row": candidate.get("row_id"),
                                        "Score": candidate.get("score"),
                                        "Title": candidate.get("title"),
                                        "Authors": candidate.get("authors"),
                                        "Year": candidate.get("year"),
                                        "Rank": candidate.get("rank"),
                                    }
                                )

                    st.subheader("Proposal")
                    st.markdown(f"### {current['column']}")
                    review = reviews.get(current["proposal_id"])
                    state = _proposal_state(current, review)
                    st.write(f"Status: {state}")
                    current_value = ""
                    normalized_column = _normalize_column_name(current.get("column", ""))
                    resolved_column = column_map.get(normalized_column)
                    row_index = row_data.get("row_index")
                    if resolved_column is not None and row_index in table.dataframe.index:
                        current_value = table.dataframe.loc[row_index, resolved_column]
                    st.write("Current value:", current_value)
                    st.write("Proposed value:", current.get("proposed_value"))
                    st.write("Confidence:", current.get("confidence"))

                    evidence_items = current.get("evidence", [])
                    if evidence_items:
                        st.markdown("**Evidence summary**")
                        for evidence in evidence_items:
                            st.write(_evidence_label(evidence))

                    needs_more_value = st.toggle(
                        "Mark as needs more evidence",
                        value=bool(current["flags"].get("needs_more_evidence")),
                        key=f"needs-more-{current['proposal_id']}",
                    )
                    if needs_more_value != bool(current["flags"].get("needs_more_evidence")):
                        if needs_more_value:
                            current["flags"]["needs_more_evidence"] = True
                        else:
                            current["flags"].pop("needs_more_evidence", None)
                        store.update_proposal_flags(current["proposal_id"], current["flags"])

                    edit_mode = st.toggle(
                        "Accept with edit",
                        value=False,
                        key=f"edit-mode-{current['proposal_id']}",
                    )
                    manual_value_default = (
                        review["final_value"]
                        if review and review["final_value"] is not None
                        else current.get("proposed_value") or ""
                    )
                    manual_value = st.text_input(
                        "Edited value",
                        value=manual_value_default,
                        disabled=not edit_mode,
                        key=f"manual-{current['proposal_id']}",
                    )
                    note = st.text_area(
                        "Note",
                        value=review["note"] if review else "",
                        key=f"note-{current['proposal_id']}",
                    )

                    st.session_state["review_auto_advance"] = st.toggle(
                        "Auto-advance",
                        value=st.session_state["review_auto_advance"],
                        key="review_auto_advance",
                    )

                    col_prev, col_next = st.columns(2)
                    with col_prev:
                        if st.button("← Prev", key=f"prev-{row_id}"):
                            st.session_state[index_key] = max(current_index - 1, 0)
                    with col_next:
                        if st.button("Next →", key=f"next-{row_id}"):
                            st.session_state[index_key] = min(current_index + 1, len(row_proposals) - 1)

                    decision_col1, decision_col2, decision_col3 = st.columns(3)
                    with decision_col1:
                        if st.button("Accept", key=f"accept-{current['proposal_id']}"):
                            store.insert_review(
                                {
                                    "review_id": current["proposal_id"],
                                    "proposal_id": current["proposal_id"],
                                    "decision": "accepted",
                                    "final_value": current.get("proposed_value"),
                                    "note": note,
                                }
                            )
                            st.success("Accepted")
                            if st.session_state["review_auto_advance"]:
                                st.session_state[index_key] = min(current_index + 1, len(row_proposals) - 1)
                    with decision_col2:
                        if st.button(
                            "Accept with edit",
                            key=f"accept-edit-{current['proposal_id']}",
                            disabled=not edit_mode,
                        ):
                            store.insert_review(
                                {
                                    "review_id": current["proposal_id"],
                                    "proposal_id": current["proposal_id"],
                                    "decision": "accepted",
                                    "final_value": manual_value,
                                    "note": note,
                                }
                            )
                            st.success("Accepted with edit")
                            if st.session_state["review_auto_advance"]:
                                st.session_state[index_key] = min(current_index + 1, len(row_proposals) - 1)
                    with decision_col3:
                        if st.button("Reject", key=f"reject-{current['proposal_id']}"):
                            store.insert_review(
                                {
                                    "review_id": current["proposal_id"],
                                    "proposal_id": current["proposal_id"],
                                    "decision": "rejected",
                                    "final_value": "",
                                    "note": note,
                                }
                            )
                            st.warning("Rejected")
                            if st.session_state["review_auto_advance"]:
                                st.session_state[index_key] = min(current_index + 1, len(row_proposals) - 1)

                    total = row_totals.get(row_id, {}).get("total", len(row_proposals))
                    decided = row_totals.get(row_id, {}).get("decided", 0)
                    st.caption(f"Row completion: {_get_row_completion(total, decided)}")

                    if decided >= total and st.button("Mark row complete"):
                        st.success("Row marked complete")

                with right_col:
                    st.subheader("PDF viewer")
                    evidence_items = current.get("evidence", [])
                    if evidence_items:
                        evidence_index = st.radio(
                            "Evidence", list(range(len(evidence_items))),
                            format_func=lambda idx: _evidence_label(evidence_items[idx]),
                            key=f"evidence-{current['proposal_id']}"
                        )
                        evidence = evidence_items[evidence_index]
                        st.write("Quote:", evidence.get("quote"))
                        st.write("Page:", evidence.get("page"))
                        st.button("Go to location", key=f"go-to-{current['proposal_id']}")
                        rects = evidence.get("rects") or []
                        pdf_path = pdf_map.get(current.get("pdf_id"))
                        parse_source = pdf_meta.get(current.get("pdf_id"), {}).get("parse_source")
                        if parse_source == "ocr":
                            st.caption("OCR enabled: highlights may be approximate.")
                        if pdf_path and evidence.get("page"):
                            image = render_page_image(pdf_path, int(evidence["page"]), rects)
                            st.image(image, caption=f"PDF page {evidence['page']}")
                            st.caption(
                                "Highlight status: highlighted" if rects else "Highlight status: not found"
                            )
                            if not rects:
                                st.warning("Highlight not found. You can re-locate the quote.")
                                if st.button("Try re-locate", key=f"relocate-{current['proposal_id']}"):
                                    tokens_path = (
                                        Path(selected_run.run_dir)
                                        / "artifacts"
                                        / "parsed"
                                        / f"{current['pdf_id']}_tokens.jsonl"
                                    )
                                    tokens = []
                                    if tokens_path.exists():
                                        tokens = [json.loads(line) for line in tokens_path.read_text(encoding="utf-8").splitlines() if line]
                                    highlight = locate_quote(
                                        pdf_path,
                                        evidence.get("quote", ""),
                                        int(evidence.get("page", 1)),
                                        locator_hint=evidence.get("locator_hint"),
                                        tokens=tokens,
                                    )
                                    evidence["rects"] = highlight.rects
                                    if highlight.found:
                                        current["flags"].pop("needs_more_evidence", None)
                                    else:
                                        current["flags"]["needs_more_evidence"] = True
                                    store.update_proposal_evidence(current["proposal_id"], evidence_items, current["flags"])
                                    st.success("Re-locate attempted")
                        else:
                            st.info("Select evidence with a page to preview the PDF.")
                    else:
                        st.info("No evidence available for this proposal.")

                st.divider()
                st.subheader("Export updated table")
                if st.checkbox("I confirm export settings"):
                    if st.button("Export updated table"):
                        export_run(Path(selected_run.run_dir))
                        st.success("Export completed")


with advanced_tab:
    st.header("Advanced")
    runs = st.session_state.get("runs", [])
    run_labels = [run.label for run in runs]
    selected_label = st.selectbox("Run", run_labels, key="advanced-run") if run_labels else None
    if selected_label:
        run_dir = runs[run_labels.index(selected_label)].run_dir
        store = Store.init_db(run_dir / "proposals.sqlite")

        st.subheader("Matching diagnostics")
        rows = [dict(row) for row in store.fetch_rows()]
        row_options = [row["row_id"] for row in rows]
        row_filter = st.selectbox("Row", row_options, key="advanced-row") if row_options else None
        candidates = [dict(row) for row in store.fetch_match_candidates()]
        if row_filter:
            candidates = [candidate for candidate in candidates if candidate.get("row_id") == row_filter]
        if candidates:
            st.dataframe(candidates)
        else:
            st.info("No match candidates recorded yet.")

        st.subheader("Retrieval diagnostics")
        pdfs = store.list_pdfs()
        pdf_options = {pdf["pdf_id"]: pdf["pdf_id"] for pdf in pdfs}
        pdf_id = st.selectbox("PDF", list(pdf_options.keys()), key="debug-pdf") if pdf_options else None
        run_config = json.loads((run_dir / "run_config.json").read_text(encoding="utf-8"))
        specs = load_schema(
            _resolve_schema_source(
                run_config.get("schema_mode", "sheet"),
                Path(run_config["table_path"]),
                Path(run_config["schema_path"]) if run_config.get("schema_path") else None,
            ),
            run_config["schema_sheet_name"],
        )
        column_options = [spec.column_name for spec in specs]
        column = st.selectbox("Column", column_options, key="debug-column") if column_options else None
        query_mode = st.selectbox(
            "Query preset",
            ["Column name", "Column description", "Column name + description"],
            key="debug-query-mode",
        )
        query = None
        if column:
            description = next((spec.description for spec in specs if spec.column_name == column), "")
            if query_mode == "Column name":
                query = column
            elif query_mode == "Column description":
                query = description
            else:
                query = f"{column}: {description}"
        if st.button("Retrieve") and run_dir and pdf_id and query:
            index = load_index(Path(run_dir) / "artifacts" / "retrieval_indexes" / pdf_id)
            if not index:
                st.error("Retrieval index not found for that PDF.")
            else:
                retrieval = run_config.get("retrieval", {})
                retrieval_config = RetrievalConfig(
                    top_k=retrieval.get("top_k", 12),
                    rerank_k=retrieval.get("rerank_k", 12),
                    max_context_chunks=retrieval.get("max_context_chunks", 16),
                    max_context_tokens=retrieval.get("max_context_tokens", 1800),
                    query_variants=retrieval.get("query_variants", 4),
                    use_query_expansion=retrieval.get("use_query_expansion", True),
                    use_hyde=retrieval.get("use_hyde", True),
                    rrf_k=retrieval.get("rrf_k", 60),
                    use_reranker=retrieval.get("use_reranker", True),
                    embedding_backend=retrieval.get("embedding_backend", "tfidf"),
                    embedding_model=retrieval.get("embedding_model"),
                    reranker_backend=retrieval.get("reranker_backend", "tfidf"),
                    reranker_model=retrieval.get("reranker_model"),
                )
                embedder = _build_embedding_client(
                    run_config.get("provider", {}).get("base_url", ""),
                    run_config.get("provider", {}).get("api_key"),
                    retrieval_config.embedding_backend,
                    retrieval_config.embedding_model,
                )
                reranker_embedder = None
                if retrieval_config.use_reranker:
                    reranker_embedder = _build_embedding_client(
                        run_config.get("provider", {}).get("base_url", ""),
                        run_config.get("provider", {}).get("api_key"),
                        retrieval_config.reranker_backend,
                        retrieval_config.reranker_model,
                    )
                if retrieval_config.embedding_backend == "lmstudio" and embedder is None:
                    st.error("LM Studio embedding backend requires an embedding model.")
                    st.stop()
                if retrieval_config.use_reranker and retrieval_config.reranker_backend == "lmstudio" and reranker_embedder is None:
                    st.error("LM Studio reranker backend requires a reranker model.")
                    st.stop()
                context = retrieve_context(
                    index,
                    query,
                    retrieval_config,
                    embedder=embedder,
                    reranker_embedder=reranker_embedder,
                )
                for chunk in context.chunks:
                    st.write(
                        chunk.chunk_id,
                        f"score {chunk.score:.3f}",
                        f"pages {chunk.page_start}-{chunk.page_end}",
                    )
                    st.code(chunk.text[:800])

        st.subheader("LLM I/O")
        st.info("Prompts and JSON outputs are stored in run logs; surface coming soon.")

        st.subheader("Evidence locator tool")
        quote = st.text_input("Quote")
        page = st.number_input("Page", min_value=1, value=1)
        if st.button("Locate quote") and pdf_id and quote:
            pdf_path = next((pdf["path"] for pdf in pdfs if pdf["pdf_id"] == pdf_id), None)
            if pdf_path:
                result = locate_quote(pdf_path, quote, int(page))
                st.write(result)
            else:
                st.error("PDF not found in run.")


with help_tab:
    st.header("Help & Troubleshooting")
    st.subheader("How to get started in 3 steps")
    st.markdown(
        """
        1. **Pick your table and PDF folder** in the Run tab.
        2. **Start a run** and wait for completion.
        3. **Review proposals** row-by-row and export the updated table.
        """
    )

    st.subheader("Common failure modes")
    st.markdown(
        """
        - **No proposals appear** → confirm schema sheet/columns, ensure PDFs parsed successfully, and check run logs.
        - **Highlight missing** → use *Try re-locate* or enable OCR fallback for scanned PDFs.
        - **Ambiguous mapping** → review matching diagnostics in the Advanced tab and adjust schema identifiers.
        """
    )

    st.subheader("Where to find artifacts")
    st.markdown("Runs are stored under `runs/<run_id>/` with logs, DB, exports, and retrieval indexes.")
