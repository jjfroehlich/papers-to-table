from __future__ import annotations

import os
import pathlib
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from ..artifacts import get_run_dir, read_json, write_json


def open_in_local_viewer(path: pathlib.Path) -> None:
    if sys.platform.startswith('win'):
        os.startfile(str(path))  # type: ignore[attr-defined]
        return
    if sys.platform == 'darwin':
        subprocess.Popen(['open', str(path)])
        return
    subprocess.Popen(['xdg-open', str(path)])


def resolve_path_like(value: str, base_dir: pathlib.Path) -> str:
    candidate = pathlib.Path(value)
    if candidate.is_absolute():
        return str(candidate.resolve())
    return str((base_dir / candidate).resolve())


def validate_output_dir_access(output_dir: str) -> pathlib.Path:
    requested = pathlib.Path(output_dir).resolve()
    enforce = os.environ.get("P2T_ENFORCE_OUTPUT_ROOT_POLICY", "").lower() in {"1", "true", "yes"}
    if not enforce:
        return requested
    allowed_roots = os.environ.get("P2T_ALLOWED_OUTPUT_ROOTS", "./runs").split(os.pathsep)
    allowed = [(pathlib.Path(root).resolve()) for root in allowed_roots if root.strip()]
    if not any(requested == root or root in requested.parents for root in allowed):
        raise HTTPException(
            status_code=403,
            detail=(
                f"output_dir '{requested}' is outside allowed roots. "
                "Set P2T_ALLOWED_OUTPUT_ROOTS to opt into additional trusted output locations."
            ),
        )
    return requested


def ensure_local_host_action_allowed(client_host: str | None) -> None:
    if os.environ.get("P2T_ALLOW_NONLOCAL_HOST_ACTIONS", "").lower() in {"1", "true", "yes"}:
        return
    trusted_hosts = {"127.0.0.1", "::1", "localhost"}
    if client_host not in trusted_hosts:
        raise HTTPException(
            status_code=403,
            detail="Host OS viewer actions are disabled for non-local clients. Use trusted loopback access or set P2T_ALLOW_NONLOCAL_HOST_ACTIONS=true.",
        )


def staged_root(output_dir: str) -> pathlib.Path:
    return pathlib.Path(output_dir).resolve() / '.staged_inputs'


def staged_metadata_path(output_dir: str, handle: str) -> pathlib.Path:
    return staged_root(output_dir) / handle / 'metadata.json'


def load_staged_input_metadata(output_dir: str, handle: str, expected_kind: str) -> dict[str, Any]:
    meta_path = staged_metadata_path(output_dir, handle)
    if not meta_path.exists():
        raise HTTPException(status_code=422, detail=f'Unknown staged input handle: {handle}')
    metadata = read_json(meta_path)
    if metadata.get('kind') != expected_kind:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Staged handle '{handle}' is for kind={metadata.get('kind')}, "
                f'but {expected_kind} was requested.'
            ),
        )
    runtime_locator = metadata.get('runtime_locator')
    if not runtime_locator:
        raise HTTPException(status_code=422, detail=f"Staged handle '{handle}' has no runtime locator.")
    return metadata


async def materialize_staged_input_files(
    *,
    kind: str,
    output_dir: str,
    files: list[UploadFile],
) -> dict[str, str]:
    allowed_kinds = {'table_path', 'schema_path', 'pdf_dir'}
    if kind not in allowed_kinds:
        raise HTTPException(status_code=422, detail=f'Invalid staged input kind: {kind}')
    if not files:
        raise HTTPException(status_code=422, detail='No files were uploaded for staging.')
    if kind in {'table_path', 'schema_path'} and len(files) != 1:
        raise HTTPException(status_code=422, detail=f'{kind} staging expects exactly one file.')

    handle = f'staged_{kind}_{uuid4().hex[:12]}'
    staged_dir = staged_root(output_dir) / handle
    staged_dir.mkdir(parents=True, exist_ok=True)

    persisted_names: list[str] = []
    if kind == 'pdf_dir':
        runtime_dir = staged_dir / 'pdf_dir'
        runtime_dir.mkdir(parents=True, exist_ok=True)
        for upload in files:
            filename = pathlib.Path(upload.filename or 'upload.pdf').name
            if not filename.lower().endswith('.pdf'):
                continue
            destination = runtime_dir / filename
            destination.write_bytes(await upload.read())
            persisted_names.append(filename)
            await upload.close()
        if not persisted_names:
            raise HTTPException(status_code=422, detail='pdf_dir staging requires at least one PDF file.')
        logical_source = f"{len(persisted_names)} picked PDF(s): " + ', '.join(persisted_names[:3])
        runtime_locator = str(runtime_dir.resolve())
    else:
        upload = files[0]
        filename = pathlib.Path(upload.filename or 'upload').name
        destination = staged_dir / filename
        destination.write_bytes(await upload.read())
        await upload.close()
        persisted_names = [filename]
        logical_source = filename
        runtime_locator = str(destination.resolve())

    metadata = {
        'handle': handle,
        'kind': kind,
        'logical_source': logical_source,
        'runtime_locator': runtime_locator,
        'persisted_names': persisted_names,
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
    write_json(staged_dir / 'metadata.json', metadata)
    return metadata


def read_run_or_404(run_id: str, output_dir: str) -> dict[str, Any]:
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f'Run not found: {run_id}')
    return read_json(run_dir / 'run.json')
