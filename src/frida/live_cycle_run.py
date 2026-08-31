"""Explicit local Glass Hood runner.  No automatic scheduler or retry loop."""
from __future__ import annotations
import argparse, json, os
from .live_observation import LiveObservationCycle
from .staging import StagingService

def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--cycles", type=int, required=True); parser.add_argument("--execute", action="store_true")
    args=parser.parse_args()
    if args.cycles != 3 or not args.execute:
        raise SystemExit("Glass Hood requires exactly --cycles 3 --execute under this Phase 1 clearance")
    service=StagingService(os.environ.get("FRIDA_DATABASE_PATH", "data/frida-golden-path.sqlite3"))
    try: print(json.dumps([LiveObservationCycle(service).run_once() for _ in range(3)], indent=2))
    finally: service.store.close()

if __name__ == "__main__": main()
