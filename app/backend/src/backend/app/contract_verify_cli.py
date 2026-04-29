from __future__ import annotations
import argparse
import json
from pathlib import Path

from .contract_verify import verify_run_bundle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate run-bundle artifact contracts")
    parser.add_argument("--run", required=True, help="Path to run bundle directory")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args(argv)

    result = verify_run_bundle(Path(args.run).resolve())
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["ok"]:
            counts = result.get("counts", {})
            print("Contract verification passed.")
            print(f"proposals={counts.get('proposals',0)} evidence={counts.get('evidence',0)} decisions={counts.get('decisions',0)} audit_logs={counts.get('audit_logs',0)}")
        else:
            print("Contract verification failed:")
            for err in result.get("errors", []):
                print(f"- {err}")
            for warn in result.get("warnings", []):
                print(f"- warning: {warn}")
    return 0 if result["ok"] else 1

if __name__ == '__main__':
    raise SystemExit(main())
