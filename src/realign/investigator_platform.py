"""Select the supported security runtime; never weaken a failed sandbox.

The native Windows LPAC prototype fails the private-registry probe. User-facing
investigator commands therefore execute this same application through Ubuntu/WSL.
There is still one investigator and one isolated numerical worker, not a service.
"""
import os
from pathlib import Path
import subprocess
import sys

SCRIPTS={'run_investigator.py','verify_investigator.py','calibrate_investigator.py',
         'replay_investigation.py','setup_investigator_runtime.py'}
SCRIPTS.update({'prepare_demo.py','verify_task05.py'})


def linux_path(value):
    if len(value)>2 and value[1]==':' and value[0].isalpha():
        return '/mnt/'+value[0].lower()+'/'+value[3:].replace('\\','/')
    return value


def delegate(script):
    if os.name!='nt':
        return
    if script not in SCRIPTS:
        raise ValueError('unapproved runtime entrypoint')
    root=Path(__file__).resolve().parents[2]
    mapped=linux_path(str(root))
    command=['wsl.exe','-d','Ubuntu','--cd',mapped,'--exec','python3',mapped+'/scripts/_wsl_entry.py',
             script,*[linux_path(a) for a in sys.argv[1:]]]
    # Credentials travel only in a local process environment, never arguments,
    # source, reports or the numerical worker's stripped environment.
    env=dict(os.environ)
    if os.environ.get('MODEL_API_KEY'):
        env['WSLENV']='MODEL_API_KEY/u'
    else:
        env.pop('WSLENV',None)
    raise SystemExit(subprocess.run(command,env=env).returncode)
