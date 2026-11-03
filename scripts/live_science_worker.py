"""Fixed WSL bridge. No camera, network client, credentials or alternate physics."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from realign.tools.sandbox import WorkerClient
from realign.audit.chain import canonical


def main():
    with WorkerClient() as worker:
        print(canonical({'status': 'READY', 'isolation': worker.isolation, 'probe': worker.probe}).decode(), flush=True)
        for line in sys.stdin.buffer:
            if len(line) > 4_000_000: return 1
            try:
                request = json.loads(line)
                result = worker.request(request)
                response = {'ok': True, 'result': result}
            except Exception as exc:
                response = {'ok': False, 'error_type': type(exc).__name__}
            print(canonical(response).decode(), flush=True)
    return 0


if __name__ == '__main__': raise SystemExit(main())
