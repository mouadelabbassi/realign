"""Offline scripted replay capture, labelled fallback; not an owner live demo."""
import argparse,json,os,sys,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))

def capture(output):
    from playwright.sync_api import sync_playwright
    from realign.product.server import make_server
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    server=make_server(ROOT/'artifacts/task05/demo',port=0,media={})
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    url='http://127.0.0.1:'+str(server.server_port)
    try:
        with sync_playwright() as p:
            kwargs={'headless':True,'env':{k:v for k,v in os.environ.items() if k!='MODEL_API_KEY'}}
            if os.environ.get('REALIGN_BROWSER_EXECUTABLE'):kwargs['executable_path']=os.environ['REALIGN_BROWSER_EXECUTABLE']
            browser=p.chromium.launch(**kwargs)
            context=browser.new_context(viewport={'width':1440,'height':1000},record_video_dir=str(output))
            context.route('**/*',lambda r:r.continue_() if r.request.url.startswith(url+'/') else r.abort())
            page=context.new_page();page.goto(url);page.wait_for_selector('#time-scrubber')
            page.evaluate("document.querySelector('.local-label').textContent='SCRIPTED OFFLINE REPLAY · FALLBACK ONLY'")
            page.locator('#run-select').select_option('live-02')
            for view in ['reality','investigation','experiment','decision','evidence']:
                page.locator('[data-view="'+view+'"]').click()
                if view=='reality':page.locator('#time-scrubber').fill('15')
                if view=='evidence':page.get_by_text('Independent validation exercise',exact=True).scroll_into_view_if_needed()
                page.wait_for_timeout(2000)
                page.screenshot(path=str(output/(view+'.png')),full_page=True)
            context.close();browser.close()
    finally:server.shutdown();server.server_close();thread.join(timeout=5)
    (output/'CAPTURE_NOTICE.json').write_text(json.dumps({'status':'SCRIPTED_OFFLINE_REPLAY_FALLBACK',
        'owner_continuous_narrated_demo':'BLOCKED_INPUTS','external_pixels':False,'meta_calls':0,
        'source_views':['reality','investigation','experiment','decision','evidence']},indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,default=ROOT/'data/processed/release_capture')
    capture(p.parse_args().output_dir)
