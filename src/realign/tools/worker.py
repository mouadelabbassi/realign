"""Private JSON-line worker protocol. Only five calls are exposed to the model."""
import json
import os
import socket
import sys
from realign.contracts.investigation import Budget, ExperimentCandidate
from realign.audit.chain import canonical
from .registry import ToolRegistry


def isolation_probe(paths):
    if not isinstance(paths,list) or not 1<=len(paths)<=4 or any(not isinstance(p,str) for p in paths):
        raise ValueError('invalid probe')
    denied=[]
    for p in paths:
        try:
            with open(p,'rb') as f:
                f.read(1)
            denied.append(False)
        except PermissionError:
            denied.append(True)
    network_denied=False
    try:
        with socket.socket() as s:
            s.settimeout(.2); s.connect(('1.1.1.1',443))
    except PermissionError:
        network_denied=True
    import importlib.util
    write_denied=False
    try:
        with open(__file__+'.write_probe','wb'):
            pass
    except PermissionError:
        write_denied=True
    memory_denied=False
    registry_denied=True
    import ctypes as c
    if os.name=='nt':
        k=c.WinDLL('kernel32',use_last_error=True)
        k.OpenProcess.argtypes=[c.c_ulong,c.c_int,c.c_ulong]; k.OpenProcess.restype=c.c_void_p
        h=k.OpenProcess(0x10,False,os.getppid())
        memory_denied=not h
        if h:
            k.CloseHandle.argtypes=[c.c_void_p]; k.CloseHandle(h)
        import winreg
        from ctypes import wintypes as w
        adv=c.WinDLL('advapi32',use_last_error=True)
        k.GetCurrentProcess.restype=c.c_void_p
        adv.OpenProcessToken.argtypes=[c.c_void_p,w.DWORD,c.POINTER(c.c_void_p)]
        token=c.c_void_p()
        if not adv.OpenProcessToken(k.GetCurrentProcess(),8,c.byref(token)):
            raise PermissionError('token verification failed')
        try:
            size=w.DWORD()
            adv.GetTokenInformation.argtypes=[c.c_void_p,w.INT,c.c_void_p,w.DWORD,c.POINTER(w.DWORD)]
            adv.GetTokenInformation(token,1,None,0,c.byref(size))
            buf=c.create_string_buffer(size.value)
            if not adv.GetTokenInformation(token,1,buf,size,c.byref(size)):
                raise PermissionError('token verification failed')
            sid=c.c_void_p.from_buffer(buf).value
            value=w.LPWSTR()
            adv.ConvertSidToStringSidW.argtypes=[c.c_void_p,c.POINTER(w.LPWSTR)]
            if not adv.ConvertSidToStringSidW(sid,c.byref(value)):
                raise PermissionError('SID verification failed')
            user_sid=value.value
            k.LocalFree.argtypes=[c.c_void_p]; k.LocalFree(c.cast(value,c.c_void_p))
            try:
                with winreg.OpenKey(winreg.HKEY_USERS,user_sid+'\\Environment',0,winreg.KEY_READ):
                    registry_denied=False
            except (PermissionError,FileNotFoundError):
                registry_denied=True
        finally:
            k.CloseHandle.argtypes=[c.c_void_p]; k.CloseHandle(token)
    else:
        libc=c.CDLL(None,use_errno=True)
        memory_denied=libc.syscall(310,os.getppid(),0,0,0,0,0)==-1 and c.get_errno()==1
    result={'filesystem_denied':denied,'network_denied':network_denied,
            'generator_import_unavailable':importlib.util.find_spec('realign.synth') is None,
            'credential_environment_absent':'MODEL_API_KEY' not in os.environ,
            'runtime_write_denied':write_denied,'parent_memory_denied':memory_denied,
            'user_environment_registry_denied':registry_denied}
    return result


def main(isolation):
    registry=None; verified=False
    print(json.dumps({'status':'READY','isolation':isolation}),flush=True)
    for line in sys.stdin.buffer:
        if len(line)>4_000_000:
            break
        try:
            request=json.loads(line)
            command=request.get('command')
            if command=='probe' and set(request)=={'command','paths'}:
                answer=isolation_probe(request['paths'])
                verified=all(answer['filesystem_denied']) and all(v for k,v in answer.items() if k!='filesystem_denied')
            elif not verified:
                raise PermissionError('isolation must be verified first')
            elif command=='reset' and set(request)=={'command','records','nominal','budget','checks','gate'}:
                registry=None
                registry=ToolRegistry(request['records'],request['nominal'],
                    budget=Budget.model_validate_json(canonical(request['budget'])),
                    checks=request['checks'],gate=request['gate'])
                answer={'nominal_model_ref':registry.nominal_ref,'trial_refs':list(registry.trial_refs),
                        'budget_ref':registry.budget_ref,'protocol_ref':registry.protocol_ref,
                        'checks_ref':registry.checks_ref,'used':dict(registry.used)}
            elif registry is None:
                raise ValueError('session not initialized')
            elif command=='candidates' and set(request)=={'command','candidates'}:
                registry.register_candidates(request['candidates'])
                answer={'registered':len(registry.candidates)}
            elif command=='admit' and set(request)=={'command','records','checks'}:
                registry.admit(request['records'],request['checks'])
                answer={'trial_refs':list(registry.trial_refs),'checks_ref':registry.checks_ref}
            elif command=='call' and set(request)=={'command','name','arguments'}:
                answer=registry.dispatch(request['name'],request['arguments'])
            elif command=='audit' and set(request)=={'command'}:
                answer={'events':registry.audit.events,'head':registry.audit.head,'used':dict(registry.used)}
            elif command=='freeze' and set(request)=={'command','model_ref'}:
                if registry.frozen:
                    raise PermissionError('already frozen')
                model=registry.model(request['model_ref']) if request['model_ref'] else None
                registry.frozen=True
                answer={'model':{'family':model['family'],'params':model['params']} if model else None,
                        'audit_head':registry.audit.head,
                        'fitted_models':list(registry.fit_cache.values()),
                        'comparisons':list(registry.comparison_cache.values())}
            else:
                raise PermissionError('private protocol command rejected')
            print(canonical({'ok':True,'result':answer}).decode(),flush=True)
        except Exception as exc:
            print(json.dumps({'ok':False,'error_type':type(exc).__name__}),flush=True)


if __name__=='__main__':
    raise SystemExit('use the isolated bootstrap')
