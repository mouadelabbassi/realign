"""Explicit loopback capture and separately authorized bounded AI routes."""
from http.server import BaseHTTPRequestHandler
import json
from pathlib import Path
import re
import secrets
import threading
from urllib.parse import urlsplit, parse_qs

from realign.product.server import LoopbackServer
from realign.product.static_assets import shared_assets
from realign.audit.terminal import emit

STATIC = Path(__file__).resolve().parents[1] / 'product' / 'static'
CSP = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self'; font-src 'self'; media-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"


def make_lab_server(controller, *, port=8770):
    token = secrets.token_urlsafe(32)
    actions = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass

        def trusted(self):
            host = self.headers.get('Host', '')
            expected = (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')
            origin = self.headers.get('Origin')
            return (host in expected and (not origin or origin == 'http://' + host)
                    and self.headers.get('Sec-Fetch-Site') not in ('cross-site',))

        def send(self, data, kind='application/json', status=200):
            if kind == 'application/json': data = json.dumps(data, allow_nan=False).encode()
            self.send_response(status)
            for key, value in {'Content-Type': kind, 'Content-Length': str(len(data)),
                'Cache-Control': 'no-store', 'Content-Security-Policy': CSP,
                'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer'}.items():
                self.send_header(key, value)
            self.end_headers()
            try: self.wfile.write(data)
            except ConnectionError: pass

        def do_GET(self):
            if not self.trusted(): return self.send({'error': 'FOREIGN_ORIGIN'}, status=403)
            path = urlsplit(self.path).path
            assets = {'/': ('live_lab.html', 'text/html; charset=utf-8'),
                      '/live_lab.js': ('live_lab.js', 'text/javascript; charset=utf-8'),
                      '/live_lab.css': ('live_lab.css', 'text/css; charset=utf-8')}
            assets.update(shared_assets(STATIC))
            if path in assets:
                name, kind = assets[path]
                return self.send((STATIC / name).read_bytes(), kind)
            if path == '/api/status': return self.send({**controller.snapshot(), 'control_token': token})
            if path == '/api/recordings': return self.send(controller.library.catalog())
            if path == '/api/investigations':
                from .live_investigation import inspect_interrupted
                return self.send({'sessions': inspect_interrupted(controller.library.root)})
            if path == '/processed.jpg':
                live = controller.live
                window = parse_qs(urlsplit(self.path).query).get('window', [None])[0]
                jpeg = (live.processed_frames.get(window) if window else live.processed_jpeg) if live else None
                return self.send(jpeg or b'', 'image/jpeg', status=200 if jpeg else 404)
            if path == '/preview.jpg':
                with controller.lock: jpeg = controller.jpeg
                return self.send(jpeg or b'', 'image/jpeg', status=200 if jpeg else 404)
            if path == '/sam-frame.jpg':
                live = controller.live
                with live.lock if live else controller.lock:
                    jpeg = live.overlay_jpeg if live else None
                return self.send(jpeg or b'', 'image/jpeg',status=200 if jpeg else 404)
            match = re.fullmatch(r'/files/(clip-[a-f0-9]{32})/(frame-\d+\.png|recording\.mp4|phone_manifest\.draft\.json|report\.json)', path)
            if match:
                folder = controller.library.root / match[1]
                try:
                    report = json.loads((folder / 'report.json').read_text(encoding='utf-8'))
                    from realign.perception.video import file_sha256
                    if file_sha256(folder / 'recording.mp4') != report['video_sha256']:
                        return self.send({'error': 'EVIDENCE_CHANGED'}, status=422)
                    file = folder / match[2]
                    kind = 'image/png' if file.suffix == '.png' else 'video/mp4' if file.suffix == '.mp4' else 'application/octet-stream'
                    return self.send(file.read_bytes(), kind)
                except (OSError, ValueError, KeyError): pass
            self.send({'error': 'NOT_FOUND'}, status=404)

        def do_POST(self):
            if not self.trusted() or not secrets.compare_digest(self.headers.get('X-Live-Lab-Token', ''), token):
                return self.send({'error': 'CONTROL_AUTHORIZATION_REQUIRED'}, status=403)
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.send({'error': 'JSON_REQUIRED'}, status=415)
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 8192: raise ValueError('bounded JSON body required')
                body = json.loads(self.rfile.read(length))
                if type(body) is not dict: raise ValueError('JSON object required')
            except (ValueError, TypeError): return self.send({'error': 'INVALID_REQUEST'}, status=400)
            if urlsplit(self.path).path in ('/api/ai/stop','/api/ai/pause'):
                if controller.live is None: return self.send({'error': 'No AI investigation'}, status=409)
                if urlsplit(self.path).path == '/api/ai/stop': controller.live.stop()
                else:
                    try: controller.live.pause()
                    except ValueError as exc: return self.send({'error':str(exc)},status=409)
                return self.send(controller.live.snapshot())
            if not actions.acquire(blocking=False): return self.send({'error': 'CONTROLLER_BUSY'}, status=409)
            try:
                path = urlsplit(self.path).path
                if path == '/api/scan':
                    devices = controller.enumerate_devices(body.get('maximum',8))
                    result = {'devices':devices,'scan':controller.device_scan}
                elif path == '/api/connect': controller.connect(body.get('index')); result = controller.snapshot()
                elif path == '/api/disconnect': controller.close(); result = controller.snapshot()
                elif path in ('/api/start', '/api/import'):
                    options = {k: body[k] for k in ('role', 'operator', 'rig_id', 'response_to_request_id') if k in body}
                    if any(not isinstance(v, str) or len(v) > 200 for v in options.values()):
                        raise ValueError('Metadata must be text of at most 200 characters')
                    if path == '/api/start':
                        controller.start(**options); result = controller.snapshot()
                    else:
                        if controller.writer is not None: raise ValueError('Stop recording before importing')
                        source = body.get('path')
                        if not isinstance(source, str) or len(source) > 2048: raise ValueError('Original MP4 path required')
                        result = controller.library.import_video(source, **options)
                        with controller.lock:
                            controller.latest = result
                            controller.move('REVIEW_REQUIRED')
                elif path == '/api/stop': result = controller.stop()
                elif path == '/api/ai/start':
                    result = controller.authorize_live(body.get('authorization', {}), body.get('windowing'))
                elif path == '/api/auto-live/authorize':
                    result = controller.authorize_auto_live(body.get('authorization',{}),body.get('windowing'),body.get('metadata'))
                elif path == '/api/auto-live/go':
                    result = controller.go_live(body.get('authorization',{}),body.get('windowing'),body.get('metadata'),index=body.get('index',0))
                elif path == '/api/ai/resume':
                    if controller.live is None: raise ValueError('No AI investigation')
                    controller.live.resume(); result = controller.live.snapshot()
                elif path == '/api/ai/reselect':
                    if controller.live is None: raise ValueError('No AI investigation')
                    controller.live.reselect_target(body.get('target_prompt'),body.get('target_confirmed'),body.get('consent'))
                    result = controller.live.snapshot()
                elif path == '/api/ai/stop':
                    if controller.live is None: raise ValueError('No AI investigation')
                    controller.live.stop(); result = controller.live.snapshot()
                elif path in ('/api/ai/reason', '/api/ai/admit', '/api/ai/confirm-action'):
                    live = controller.live
                    if live is None or live.cancel.is_set(): raise ValueError('Authorize an active AI investigation first')
                    accepted = True
                    if path == '/api/ai/confirm-action': controller.confirm_action(body.get('request_id'))
                    elif path == '/api/ai/admit':
                        from realign.perception.workflow import _path
                        source = body.get('manifest')
                        if not isinstance(source, str) or not 1 <= len(source) <= 2048: raise ValueError('Local approved manifest required')
                        source = _path(source, Path.cwd())
                        if not source.is_file() or source.suffix != '.json': raise ValueError('Local JSON manifest required')
                        accepted = live.enqueue_science('admit', {'manifest': str(source)})
                    else: accepted = live.enqueue_science('operator', {})
                    result = {'status': 'CONFIRMED' if path == '/api/ai/confirm-action' else 'QUEUED' if accepted else 'COALESCED', 'investigation': live.snapshot()}
                else: return self.send({'error': 'NOT_FOUND'}, status=404)
                emit('CONTROL_COMPLETED',operation=path)
                self.send(result)
            except ValueError as exc:
                emit('CONTROL_REJECTED',operation=path,code='INVALID_CONTROL_INPUT',error_type=type(exc).__name__)
                self.send({'error': str(exc)}, status=409)
            except Exception as exc:
                emit('CONTROL_FAILED',operation=path,code='LOCAL_IO_FAILED',error_type=type(exc).__name__)
                self.send({'error': 'LOCAL_IO_FAILED; inspect disk, encoder and camera permissions'}, status=422)
            finally: actions.release()

        def do_PUT(self): self.send({'error': 'METHOD_NOT_ALLOWED'}, status=405)
        do_DELETE = do_PUT

    return LoopbackServer(('127.0.0.1', port), Handler)
