"""Fixed application entrypoints inside WSL; no arbitrary script/code execution."""
import os
from pathlib import Path
import sys
import subprocess
import venv

ALLOWED={'run_investigator.py','verify_investigator.py','calibrate_investigator.py',
         'replay_investigation.py','setup_investigator_runtime.py'}
ALLOWED.update({'prepare_demo.py','verify_task05.py'})
ALLOWED.update({'investigate_recordings.py','verify_task06.py','verify_g5.py'})
ALLOWED.add('release_check.py')
root=Path(__file__).resolve().parents[1]
name=sys.argv[1] if len(sys.argv)>1 else ''
if name not in ALLOWED:
    raise SystemExit('unapproved runtime entrypoint')
runtime=Path.home()/'.cache/realign-task04-venv'
python=runtime/'bin/python'
if name=='setup_investigator_runtime.py':
    if not python.exists():
        venv.EnvBuilder(with_pip=True).create(runtime)
    subprocess.run([str(python),'-m','pip','install','-e',str(root)+'[dev,perception]'],check=True)
    print('Supported Linux investigator runtime installed.')
    raise SystemExit(0)
if not python.exists():
    raise SystemExit('Run python scripts/setup_investigator_runtime.py first.')
env=dict(os.environ)
env['PYTHONPATH']=str(root/'src')
env['OPENBLAS_NUM_THREADS']=env['OMP_NUM_THREADS']=env['MKL_NUM_THREADS']='1'
os.chdir(root)
os.execve(str(python),[str(python),str(root/'scripts'/name),*sys.argv[2:]],env)
