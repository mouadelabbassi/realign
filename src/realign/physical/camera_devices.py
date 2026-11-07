import json
import os
import subprocess
from realign.audit.terminal import emit


def windows_cameras(maximum=16):
    import cv2
    from cv2_enumerate_cameras import enumerate_cameras
    devices = []
    succeeded = 0
    for backend in (cv2.CAP_DSHOW, cv2.CAP_MSMF):
        try:
            cameras = enumerate_cameras(backend)
            succeeded += 1
        except Exception as exc:
            emit('CAMERA_CATALOG_BACKEND_FAILED',backend_id=backend,error_type=type(exc).__name__)
            continue
        emit('CAMERA_CATALOG_DISCOVERED',backend_id=backend,detected_count=len(cameras))
        for camera in cameras:
            if not 0 <= camera.index < maximum:
                continue
            devices.append({'index': camera.index, 'backend_id': backend,
                'backend': cv2.videoio_registry.getBackendName(backend),
                'name': camera.name, 'id': f'{backend}:{camera.index}',
                'availability': 'REGISTERED; CONNECT_TO_VERIFY_FRAMES'})
    if not succeeded:
        raise RuntimeError('Windows camera enumeration failed on both backends')
    return devices


def windows_portable_devices():
    if os.name != 'nt':
        return []
    command = "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); @(Get-PnpDevice -PresentOnly -Class WPD -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FriendlyName) | ConvertTo-Json -Compress"
    try:
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
            capture_output=True, timeout=8, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            return []
        names = json.loads(result.stdout.decode('utf-8-sig'))
        if isinstance(names, str):
            names = [names]
        return [{'name': name, 'kind': 'PORTABLE_DEVICE'} for name in names or [] if isinstance(name, str)]
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return []
