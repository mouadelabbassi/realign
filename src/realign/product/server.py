"""One loopback Python application serving a read-only scientific product slice."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import mimetypes
import os,socket
from pathlib import Path
import re
from urllib.parse import urlsplit,unquote
from realign.audit.chain import canonical
from .evidence import EvidenceError,sha256_file
from .store import ProductStore

STATIC=Path(__file__).with_name('static')
ASSETS={'/':('index.html','text/html; charset=utf-8'),
        '/app.css':('app.css','text/css; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8')}
ASSETS.update({'/static/app.css':ASSETS['/app.css'],'/static/app.js':ASSETS['/app.js']})
CSP="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"

class LoopbackServer(ThreadingHTTPServer):
    # Windows SO_REUSEADDR can route traffic to an older listener after a
    # seemingly successful bind. Fail visibly instead of sharing the port.
    allow_reuse_address=os.name!='nt'
    def server_bind(self):
        if os.name=='nt':self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        super().server_bind()


def make_server(data_root,*,port=8765,media=None,closure_root=None,review_root=None):
    root=Path(data_root).resolve(); media=dict(media or {})
    closure_root=Path(closure_root) if closure_root else Path(__file__).resolve().parents[3]/'artifacts/task06'
    release_root=Path(__file__).resolve().parents[3]/'artifacts/release'
    review_root=Path(review_root) if review_root else (release_root if (release_root/'manual_review/review.html').is_file() else closure_root)
    for name,p in media.items():
        if not re.fullmatch(r'[a-zA-Z0-9_-]+\.(mp4|png)',name) or not Path(p).is_file():
            raise ValueError('invalid explicitly approved media resource')
    media={name:(Path(p),sha256_file(p)) for name,p in media.items()}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass  # Do not log query strings, request bodies or local file paths.

        def _headers(self,status,content_type,size,extra=None,policy=None):
            self.send_response(status); self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(size)); self.send_header('Cache-Control','no-store')
            self.send_header('Content-Security-Policy',policy or CSP); self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','no-referrer')
            for k,v in (extra or {}).items(): self.send_header(k,v)
            self.end_headers()

        def _json(self,value,status=200):
            from .claim_ladder import api_header,release_evidence,compute_ladder
            try:ladder=release_evidence()['ladder']
            except (OSError,ValueError,KeyError,TypeError):ladder=compute_ladder({})
            value={**value,'evidence_header':api_header(value,urlsplit(self.path).path,ladder)}
            data=canonical(value); self._headers(status,'application/json; charset=utf-8',len(data))
            self.wfile.write(data)

        def do_POST(self): self._json({'status':'READ_ONLY','message':'Use the explicit local verification command to run an investigation.'},405)
        do_PUT=do_POST
        do_DELETE=do_POST

        def do_GET(self):
            # Prevent DNS rebinding from exposing loopback evidence to other sites.
            host=self.headers.get('Host','').split(':')[0]
            if host not in ('127.0.0.1','localhost'):
                self._json({'status':'FORBIDDEN'},403); return
            origin=self.headers.get('Origin')
            if origin and urlsplit(origin).netloc!=self.headers.get('Host'):
                self._json({'status':'FORBIDDEN'},403); return
            path=unquote(urlsplit(self.path).path)
            try:
                if path in ASSETS:
                    name,kind=ASSETS[path]; data=(STATIC/name).read_bytes()
                    self._headers(200,kind,len(data)); self.wfile.write(data); return
                if path=='/api/closure':
                    from .closure import load_closure
                    self._json(load_closure(closure_root));return
                if path=='/api/release':
                    from .claim_ladder import release_view
                    self._json(release_view(review_root=review_root));return
                if path=='/review':
                    from .closure import review_page
                    data,policy=review_page(review_root)
                    self._headers(200,'text/html; charset=utf-8',len(data),policy=policy);self.wfile.write(data);return
                if path.startswith('/media/'):
                    name=path.removeprefix('/media/')
                    if name not in media:
                        self._json({'status':'NOT_FOUND'},404); return
                    p,expected=media[name]
                    if sha256_file(p)!=expected:raise EvidenceError('approved media changed')
                    self._media(p); return
                store=ProductStore(root)
                if path=='/api/catalog': self._json(store.catalog())
                elif path=='/api/status': self._json(store.status())
                elif path=='/api/external': self._json(store.external())
                elif re.fullmatch(r'/api/runs/[a-z0-9-]{1,64}',path): self._json(store.run(path.rsplit('/',1)[1]))
                else: self._json({'status':'NOT_FOUND'},404)
            except (EvidenceError,FileNotFoundError,KeyError,ValueError,TypeError,AttributeError):
                self._json({'status':'EVIDENCE_UNAVAILABLE','message':'Evidence is missing, malformed or changed. Refusing to display it as verified.'},422)
            except ConnectionError:
                pass

        def _media(self,p):
            size=p.stat().st_size; start=0; end=size-1; status=200
            value=self.headers.get('Range')
            if value:
                match=re.fullmatch(r'bytes=(\d+)-(\d*)',value)
                if not match:
                    self._headers(416,'text/plain',0,{'Content-Range':'bytes */'+str(size)}); return
                start=int(match[1]); end=min(end,int(match[2])) if match[2] else end
                if start>end or start>=size:
                    self._headers(416,'text/plain',0,{'Content-Range':'bytes */'+str(size)}); return
                status=206
            extra={'Accept-Ranges':'bytes'}
            if status==206: extra['Content-Range']=f'bytes {start}-{end}/{size}'
            self._headers(status,mimetypes.guess_type(p.name)[0] or 'application/octet-stream',end-start+1,extra)
            with p.open('rb') as f:
                f.seek(start); remaining=end-start+1
                while remaining:
                    chunk=f.read(min(65536,remaining))
                    if not chunk:break
                    self.wfile.write(chunk); remaining-=len(chunk)
    return LoopbackServer(('127.0.0.1',port),Handler)
