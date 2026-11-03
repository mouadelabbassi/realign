"""Start REALIGN's local scientific investigation interface."""
import argparse
from pathlib import Path
import subprocess
import sys
import webbrowser
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from realign.product.store import ProductStore
from realign.product.server import make_server

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port',type=int,default=8765)
    p.add_argument('--data-dir',type=Path,default=ROOT/'artifacts/task05/demo')
    p.add_argument('--no-browser',action='store_true')
    args=p.parse_args()
    if not (args.data_dir/'catalog.json').exists():
        subprocess.run([sys.executable,str(ROOT/'scripts/prepare_demo.py'),'--output-dir',str(args.data_dir)],check=True)
    store=ProductStore(args.data_dir); external=store.external(); media={}
    video=ROOT/'data/raw/external/blocked-pendulum.mp4'
    if external.get('media_url') and video.is_file():
        from realign.product.evidence import sha256_file
        if sha256_file(video)==external.get('metadata',{}).get('video_sha256'):
            media['external.mp4']=video
    server=make_server(args.data_dir,port=args.port,media=media)
    url='http://127.0.0.1:'+str(server.server_port)
    print('REALIGN:',url,flush=True)
    print('Recorded artifact playback. API calls and numerical fitting are never triggered by viewing.',flush=True)
    if not args.no_browser:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
