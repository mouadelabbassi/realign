"""Private numerical subprocess, isolated before importing scientific modules.

Linux: copied runtime + Landlock/seccomp + resource limits. Windows CLI commands
delegate to Linux/WSL. Native Windows isolation fails closed.
"""
import hashlib
import importlib.util
from importlib.metadata import version
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import threading
from realign.audit.chain import canonical, digest

ROOT=Path(__file__).resolve().parents[3]
MODULES=('__init__.py','physics/__init__.py','physics/analytic.py','physics/hybrid_pendulum.py',
    'contracts/__init__.py','contracts/video.py','contracts/external.py','contracts/investigation.py',
    'observation/__init__.py','observation/camera.py','observation/noise.py',
    'fit/__init__.py','fit/robust_fit.py','fit/peg_fit.py','fit/circle_fit.py','fit/baselines.py',
    'audit/__init__.py','audit/chain.py','tools/__init__.py','tools/resources.py',
    'tools/registry.py','tools/worker.py','tools/_linux_isolation.py')
PACKAGES=('numpy','scipy','pydantic','pydantic_core','annotated_types','typing_inspection','typing_extensions','cv2')


class IsolationUnavailable(RuntimeError):
    pass


def _copy_runtime():
    versions={'python':sys.version,'format':3}
    for p in ('numpy','scipy','pydantic'):
        versions[p]=version(p)
    versions['cv2_available']=importlib.util.find_spec('cv2') is not None
    root=Path(tempfile.gettempdir())/('realign-numerics-'+digest(versions)[:16])
    root.mkdir(exist_ok=True)
    if not (root/'complete.json').exists():
        base=Path(sys._base_executable).parent
        if os.name=='nt':
            for p in [base/'python.exe',*base.glob('*.dll')]:
                shutil.copy2(p,root/p.name)
            shutil.copytree(base/'DLLs',root/'DLLs',dirs_exist_ok=True)
        stdlib=Path(sysconfig.get_path('stdlib'))
        shutil.copytree(stdlib,root/'Lib',dirs_exist_ok=True,
            ignore=shutil.ignore_patterns('site-packages','dist-packages','__pycache__','test','tests','idlelib','tkinter','turtledemo','ensurepip'))
        packages=root/'packages'; packages.mkdir(exist_ok=True)
        for name in PACKAGES:
            spec=importlib.util.find_spec(name)
            if spec is None and name=='cv2':
                continue
            p=Path(spec.origin)
            source=p.parent if spec.submodule_search_locations else p
            target=packages/(name if spec.submodule_search_locations else p.name)
            if source.is_dir():
                shutil.copytree(source,target,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','tests'))
                for libs in source.parent.glob(name+'.libs'):
                    shutil.copytree(libs,packages/libs.name,dirs_exist_ok=True)
            else:
                shutil.copy2(source,target)
        # No editable .pth files, generators, project reports, credentials or data.
        if os.name=='nt':
            name='python'+str(sys.version_info.major)+str(sys.version_info.minor)+'._pth'
            (root/name).write_text('Lib\nDLLs\npackages\n',encoding='utf-8')
        (root/'complete.json').write_bytes(canonical(versions))
    return root


def _snapshot(root):
    h=hashlib.sha256()
    for relative in MODULES:
        p=ROOT/'src/realign'/relative
        h.update(relative.encode()); h.update(p.read_bytes())
    snapshot=root/'snapshots'/h.hexdigest()
    code=snapshot/'code/realign'
    for relative in MODULES:
        destination=code/relative; destination.parent.mkdir(parents=True,exist_ok=True)
        data=(ROOT/'src/realign'/relative).read_bytes()
        if not destination.exists():
            destination.write_bytes(data)
        if destination.read_bytes()!=data:
            raise IsolationUnavailable('runtime snapshot integrity failure')
    allowed=[str(root.resolve())]
    if os.name!='nt':
        for p in ('/lib/x86_64-linux-gnu','/usr/lib/x86_64-linux-gnu','/lib64','/etc/ld.so.cache','/dev/null','/dev/urandom','/proc/cpuinfo'):
            if Path(p).exists():
                allowed.append(str(Path(p).resolve()))
        libdir=Path(sysconfig.get_config_var('LIBDIR') or '/missing')
        for p in libdir.glob('libpython*.so*'):
            allowed.append(str(p.resolve()))
    bootstrap=snapshot/'bootstrap.py'
    source=(
        "import sys,os\n"
        "sys.path[:]=["+repr(str(snapshot/'code'))+","+repr(str(root/'Lib'))+","+
        repr(str(root/'Lib/lib-dynload'))+","+repr(str(root/'DLLs'))+","+repr(str(root/'packages'))+"]\n"
        "if os.name=='nt':\n    isolation='WINDOWS_LPAC_JOB'\n"
        "else:\n"
        "    import resource\n"
        "    resource.setrlimit(resource.RLIMIT_CORE,(0,0))\n"
        "    resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))\n"
        "    resource.setrlimit(resource.RLIMIT_CPU,(3600,3600))\n"
        "    resource.setrlimit(resource.RLIMIT_NOFILE,(64,64))\n"
        "    from realign.tools._linux_isolation import restrict\n"
        "    isolation=restrict("+repr(allowed)+")\n"
        "from realign.tools.worker import main\n"
        "main(isolation)\n")
    if not bootstrap.exists():
        bootstrap.write_text(source,encoding='utf-8')
    elif bootstrap.read_text(encoding='utf-8')!=source:
        raise IsolationUnavailable('bootstrap integrity failure')
    return bootstrap


class WorkerClient:
    def __init__(self, *, timeout_s=600):
        if os.name=='nt':
            # The tested LPAC bootstrap requires registryRead, which can access
            # private user keys. A missing probe key cannot make it secure.
            raise IsolationUnavailable('user_environment_registry_denied: native Windows is unsupported; use Linux/WSL')
        self.timeout_s=timeout_s; self._queue=queue.Queue(); self.closed=False
        root=_copy_runtime(); script=_snapshot(root)
        env={'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
        self.process=None
        try:
            if sys.platform=='linux':
                self.process=subprocess.Popen([sys.executable,'-I','-S','-B',str(script)],cwd=root,
                    env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,close_fds=True)
            else:
                raise IsolationUnavailable('supported OS isolation unavailable')
            threading.Thread(target=self._read,daemon=True).start()
            threading.Thread(target=self._discard_stderr,daemon=True).start()
            ready=self._receive()
            if ready.get('status')!='READY':
                raise IsolationUnavailable('isolated runtime did not start')
            self.isolation=ready['isolation']
            # A real forbidden-file check, not a filename substring/import check.
            self.probe=self.request({'command':'probe','paths':[str(ROOT/'AGENTS.md'),
                                                               str(ROOT/'artifacts/b3_post_fit_evaluation.json')]})
            failed=[k for k,v in self.probe.items() if not (all(v) if isinstance(v,list) else v)]
            if failed:
                raise IsolationUnavailable('failed isolation probes: '+','.join(failed))
        except Exception as exc:
            self.close()
            detail=str(exc) if isinstance(exc,IsolationUnavailable) or isinstance(exc,ValueError) and str(exc).startswith('worker rejected request:') else type(exc).__name__
            raise IsolationUnavailable('isolated worker startup failed: '+detail) from None

    def _read(self):
        while True:
            line=self.process.stdout.readline(4_000_001)
            if not line:
                self._queue.put(None); return
            if len(line)>4_000_000:
                self._queue.put(None); return
            self._queue.put(line)

    def _discard_stderr(self):
        # Raw startup/SDK/library errors can contain paths. Never persist them.
        while self.process.stderr.read(4096):
            pass

    def _receive(self):
        try:
            line=self._queue.get(timeout=self.timeout_s)
        except queue.Empty:
            self.close()
            raise IsolationUnavailable('worker operation timeout') from None
        if line is None:
            raise IsolationUnavailable('worker terminated')
        try:
            return json.loads(line)
        except (ValueError,UnicodeError):
            raise IsolationUnavailable('invalid worker output') from None

    def request(self, request):
        if self.closed:
            raise IsolationUnavailable('worker closed')
        data=canonical(request)
        if len(data)>4_000_000:
            raise ValueError('request size limit')
        self.process.stdin.write(data+b'\n')
        self.process.stdin.flush()
        response=self._receive()
        if not response.get('ok'):
            raise ValueError('worker rejected request: '+response.get('error_type','Unknown'))
        return response['result']

    def call(self, name, arguments):
        from realign.contracts.investigation import TOOLS, ToolFailure
        result=self.request({'command':'call','name':name,'arguments':arguments})
        cls=ToolFailure if 'code' in result else TOOLS[name][1]
        return cls.model_validate_json(canonical(result)).model_dump(mode='json')

    def close(self):
        if self.closed:
            return
        self.closed=True
        if self.process is not None:
            self.process.kill(); self.process.wait(timeout=5)
            for stream in (self.process.stdin,self.process.stdout,self.process.stderr):
                stream.close()

    def __enter__(self):
        return self

    def __exit__(self,*_):
        self.close()
