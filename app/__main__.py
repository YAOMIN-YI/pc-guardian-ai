import argparse
import json
from pathlib import Path
import sys
from app.service import GuardianService, default_data_dir
from app.repair.policy import ACTION_DESCRIPTION, ACTION_ID


def main(argv=None) -> int:
    # JSON piped to files must have a stable encoding on Traditional Chinese Windows.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="PC Guardian AI: CPU/mock software MVP")
    parser.add_argument("--demo", action="store_true", help="Use synthetic data; never change the host")
    parser.add_argument("--cli", action="store_true", help="Use terminal instead of PySide6")
    parser.add_argument("--network-probe", action="store_true", help="Live DNS example.com and TCP 1.1.1.1:443 tests")
    parser.add_argument("--data-dir", type=Path, default=default_data_dir())
    parser.add_argument("--backend", choices=["mock", "hailo"], default="mock")
    parser.add_argument("--repair", action="store_true", help="Preview the allowlisted Spooler repair")
    parser.add_argument("--execute", action="store_true", help="Request execution with interactive explicit consent")
    args = parser.parse_args(argv)
    if args.execute and not (args.cli and args.repair):
        parser.error("--execute requires --cli --repair")
    if args.repair and not args.cli:
        parser.error("--repair requires --cli; the GUI has its own approval dialog")
    try:
        if not args.cli:
            from app.ui import launch_gui
            return launch_gui(data_dir=args.data_dir, demo=args.demo,
                              network_probe=args.network_probe, backend_name=args.backend)
        service = GuardianService(args.data_dir, args.demo, args.network_probe, args.backend)
        result = service.scan()
        repair = None
        if args.repair:
            approved = False
            if args.execute:
                if not sys.stdin.isatty():
                    raise ValueError("Execution requires an interactive terminal. No unattended approval is supported.")
                print(f"{'SIMULATION ONLY' if args.demo else 'LIVE WINDOWS CHANGE'}: {ACTION_DESCRIPTION}")
                approved = input("Type START SPOOLER to approve this action, or Enter to cancel: ").strip() == "START SPOOLER"
            repair = service.repair(ACTION_ID, dry_run=not args.execute, approved=approved)
            result = service.last_result
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if repair and repair["status"] in ("blocked", "failed", "verification_failed", "verified_with_warning"):
            return 2
        return 0
    except (OSError, ValueError, RuntimeError, NotImplementedError, ImportError) as exc:
        print(f"PC Guardian AI: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

