"""Validate a committed revision in an isolated clean checkout, without Meta calls.

Output lives outside that checkout. No original evidence is regenerated in the
release tree. A separate checkout removes the edit-during-test source-hash race.
"""
import argparse,json,os,subprocess,sys,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))

def main():
    from realign.investigator_platform import delegate
    delegate('release_check.py')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--revision',default='HEAD');p.add_argument('--output-dir',type=Path,default=ROOT/'data/processed/release')
    p.add_argument('--baseline',action='store_true',help='Pinned pre-vFinal revision lacks the new release tests')
    args=p.parse_args();out=args.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    rev=subprocess.check_output(['git','rev-parse',args.revision],cwd=ROOT,text=True).strip()
    wt=out/('checkout-'+rev[:12]+'-'+uuid.uuid4().hex[:6])
    subprocess.run(['git','worktree','add','--detach',str(wt),rev],cwd=ROOT,check=True)
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=wt).strip()
    env={k:v for k,v in os.environ.items() if k not in ('MODEL_API_KEY','OPENAI_API_KEY','WSLENV')}
    env.update(PYTHONPATH=str(wt/'src'),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',MPLBACKEND='Agg')
    cache=Path.home()/'.cache/realign-release-checks';cache.mkdir(parents=True,exist_ok=True)
    venv=cache/('venv-'+uuid.uuid4().hex[:8]);subprocess.run([sys.executable,'-m','venv',str(venv)],check=True,env=env)
    from importlib.metadata import version
    constraints=out/'runtime_constraints.txt'
    constraints.write_text(''.join(n+'=='+version(n)+'\n' for n in ('numpy','scipy','pydantic','pytest','matplotlib','opencv-python-headless','meta-sam-parser','openai','playwright')))
    py=str(venv/'bin/python');rows=[]
    def run(name,command,extra=None):
        start=time.monotonic()
        with (out/(name+'.log')).open('w') as log:
            r=subprocess.run(command,cwd=wt,env=dict(env,**(extra or {})),stdout=log,stderr=subprocess.STDOUT)
        row={'name':name,'command':command,'exit_code':r.returncode,'elapsed_s':round(time.monotonic()-start,3)}
        rows.append(row);print(name+': '+('PASS' if r.returncode==0 else 'FAIL'),flush=True)
        save();return r.returncode==0
    def save():
        report={'source_sha':rev,'checkout':str(wt),'initial_worktree_clean':True,'meta_api_calls':0,
                'status':'PASS' if rows and all(r['exit_code']==0 for r in rows) else 'FAIL','commands':rows,
                'dependency_mode':'Isolated venv installs dependencies constrained to the verified runtime versions; editable source is the clean checkout.'}
        (out/'release_check.json').write_text(json.dumps(report,indent=2)+'\n')
    if not run('install',[py,'-m','pip','install','-c',str(constraints),'-e',str(wt)+'[dev,perception,ui-test]']):return 1
    run('full_tests',[py,'-m','pytest','-q','--tb=short','--junitxml='+str(out/'full_tests.xml')])
    run('g1',[py,'scripts/verify_g1.py'])
    for name,script in [('baselines','verify_baselines.py'),('g2','verify_g2.py'),('structural','verify_structural.py')]:
        run(name,[py,'scripts/'+script,'--output-dir',str(out/name)])
    run('g5_random_reproduction',[py,'scripts/verify_g5.py','reproduce','artifacts/task06/g5_demo'])
    run('g5_control_reproduction',[py,'scripts/verify_g5.py','reproduce','artifacts/task06/g5_positive_control'])
    browser=['tests/test_product_browser.py','tests/test_task06_browser.py']
    if not args.baseline:browser+=['tests/vfinal/test_browser.py']
    # Reuse a local installed browser executable when Playwright's cache is absent.
    browser_env={'REALIGN_BROWSER_TESTS':'1','REALIGN_SCREENSHOT_DIR':str(out/'screenshots')}
    if os.environ.get('REALIGN_BROWSER_EXECUTABLE'):browser_env['REALIGN_BROWSER_EXECUTABLE']=os.environ['REALIGN_BROWSER_EXECUTABLE']
    run('browser',[py,'-m','pytest','-q',*browser,'--junitxml='+str(out/'browser_tests.xml')],browser_env)
    import shutil,playwright
    node=shutil.which('node') or str(Path(playwright.__file__).parent/'driver/node')
    run('javascript',[node,'--check','src/realign/product/static/app.js'])
    # Tests/verifiers may write derivative evidence in this disposable checkout;
    # scientific source must remain the pinned committed content.
    changed=subprocess.check_output(['git','diff','--name-only','--','src','scripts'],cwd=wt,text=True).strip()
    rows.append({'name':'source_unchanged','exit_code':int(bool(changed))});save()
    return 0 if all(r['exit_code']==0 for r in rows) else 1

if __name__=='__main__':raise SystemExit(main())
