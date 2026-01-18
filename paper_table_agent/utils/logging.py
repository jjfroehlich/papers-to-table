from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any


def configure_logging(log_dir: Path) -> tuple[logging.Logger, Path]:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "run.log"
    logger = logging.getLogger("paper_table_agent")
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(log_path, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.handlers = [handler]
    return logger, log_path


def log_error(error_path: Path, payload: dict[str, Any]) -> None:
    error_path.parent.mkdir(parents=True, exist_ok=True)
    with error_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")
