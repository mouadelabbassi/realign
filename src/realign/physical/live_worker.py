"""Persistent stdio bridge to the SAME isolated scientific worker under WSL."""
import os
from pathlib import Path
import queue
import subprocess
import threading

from realign.investigator_platform import linux_path
from realign.tools.sandbox import WorkerClient, IsolationUnavailable


class WSLWorker(WorkerClient):
    def __init__(self, *, timeout_s=600):
        self.timeout_s = timeout_s
        self.closed = False
        self._queue = queue.Queue()
        root = Path(__file__).resolve().parents[3]
        mapped = linux_path(str(root))
        env = {k: v for k, v in os.environ.items() if k not in ('MODEL_API_KEY', 'WSLENV')}
        self.process = subprocess.Popen(['wsl.exe', '-d', 'Ubuntu', '--cd', mapped, '--exec',
            'python3', mapped + '/scripts/_wsl_entry.py', 'live_science_worker.py'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
            creationflags=subprocess.CREATE_NO_WINDOW)
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._discard_stderr, daemon=True).start()
        try:
            ready = self._receive()
            if ready.get('status') != 'READY': raise IsolationUnavailable('WSL scientific worker unavailable')
            self.isolation, self.probe = ready['isolation'], ready['probe']
            if not all(all(v) if isinstance(v, list) else v for v in self.probe.values()):
                raise IsolationUnavailable('WSL isolation probes failed')
        except Exception:
            self.close()
            raise


def scientific_worker(factory=WorkerClient, **options):
    return WSLWorker(**options) if os.name == 'nt' and factory is WorkerClient else factory(**options)
