"""Explicit native-host camera controller; offline import never needs a key."""
import argparse
import json
from pathlib import Path
import sys
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8770)
    parser.add_argument('--library', type=Path, default=ROOT / 'data/raw/live_lab')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--log-level',choices=('DEBUG','INFO','WARNING','ERROR'),default='INFO')
    parser.add_argument('--list-devices', action='store_true')
    parser.add_argument('--import-video', type=Path)
    parser.add_argument('--role', choices=('pilot', 'stationary', 'free', 'peg', 'requested_experiment'), default='pilot')
    parser.add_argument('--operator', default='')
    parser.add_argument('--rig-id', default='')
    parser.add_argument('--response-to-request-id')
    args = parser.parse_args()
    from realign.audit.terminal import configure_terminal, emit
    configure_terminal(args.log_level)
    emit('LIVE_LAB_STARTING',operation='local_controller')
    from realign.physical.live_lab import LabLibrary, CaptureController
    library = LabLibrary(args.library)
    if args.import_video:
        try:
            report = library.import_video(args.import_video, role=args.role, operator=args.operator,
                rig_id=args.rig_id, response_to_request_id=args.response_to_request_id)
        except (ValueError, OSError) as exc:
            print('Import refused:', exc); return 1
        print(json.dumps({'id': report['id'], 'status': report['status'], 'media': report['media'],
                          'blockers': report['blockers']}, indent=2))
        return 2
    controller = CaptureController(library)
    if args.list_devices:
        print(json.dumps({'devices': controller.enumerate_devices(),
                          'phone_identity': 'OPERATOR_MUST_CONFIRM'}, indent=2))
        return 0
    from realign.physical.lab_server import make_lab_server
    try: server = make_lab_server(controller, port=args.port)
    except OSError:
        print('Live Lab port unavailable. Choose --port or stop the old controller.'); return 1
    url = f'http://127.0.0.1:{server.server_port}'
    print('REALIGN Live Lab:', url, flush=True)
    print('Offline until Go Live authorizes API calls and starts capture. Connect is available for offline preview. Ctrl+C saves an interrupted clip.', flush=True)
    if not args.no_browser: webbrowser.open(url)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        controller.close()
        server.server_close()
    return 0


if __name__ == '__main__': raise SystemExit(main())
