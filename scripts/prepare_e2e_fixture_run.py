from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.config import load_config
from backend.app.runner import Runner


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Prepare deterministic e2e fixture run data.')
    parser.add_argument('--config', default='tests/fixtures/configs/test-config.json', help='Config file to load before overriding the output root.')
    parser.add_argument('--output-root', default='artifacts/e2e', help='Dedicated artifact root for the prepared e2e run.')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_root = Path(args.output_root)
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    config = load_config(args.config)
    config.paths.output_dir = str(output_root)

    run = Runner(output_root).execute(config)
    print(run.run_id)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
