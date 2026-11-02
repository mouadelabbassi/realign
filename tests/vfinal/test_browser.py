"""Opt-in release interface regression; no model calls or measurements."""
import json,os,threading
from pathlib import Path
import pytest
from realign.product.server import make_server

ROOT=Path(__file__).resolve().parents[2]
pytestmark=pytest.mark.skipif(os.environ.get('REALIGN_BROWSER_TESTS')!='1',reason='Opt-in browser checks')

@pytest.fixture(scope='module')
def app():
    from playwright.sync_api import sync_playwright
    server=make_server(ROOT/'artifacts/task05/demo',port=0)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    with sync_playwright() as p:
        args={'headless':True,'env':{k:v for k,v in os.environ.items() if k!='MODEL_API_KEY'}}
        if os.environ.get('REALIGN_BROWSER_EXECUTABLE'):args['executable_path']=os.environ['REALIGN_BROWSER_EXECUTABLE']
        browser=p.chromium.launch(**args)
        yield browser,'http://127.0.0.1:'+str(server.server_port)
        browser.close()
    server.shutdown();server.server_close();thread.join(timeout=5)

@pytest.mark.parametrize('width',[1440,390])
def test_five_views_claim_boundary_and_both_g5_outcomes(app,width):
    from playwright.sync_api import expect
    browser,url=app;context=browser.new_context(viewport={'width':width,'height':1000})
    page=context.new_page();page.goto(url);page.wait_for_selector('#time-scrubber')
    for view in ['reality','investigation','experiment','decision','evidence']:
        page.locator('[data-view="'+view+'"]').click()
        expect(page.locator('#release-header')).to_contain_text('C3a')
        expect(page.locator('#release-header')).to_contain_text('SYNTHETIC_VALIDATION_FAIL')
        expect(page.locator('#release-header')).to_contain_text('No predictive advantage demonstrated')
    expect(page.locator('#content')).to_contain_text('SYNTHETIC EXERCISE PASS')
    expect(page.locator('#content')).to_contain_text('SYNTHETIC VALIDATION FAIL')
    expect(page.locator('#content')).to_contain_text('Run locally')
    page.locator('[data-source="external"]').click()
    expect(page.locator('#content')).to_contain_text('External footage is not a REALIGN phone experiment')
    page.locator('[data-source="phone"]').click()
    expect(page.locator('#content')).to_contain_text('BLOCKED INPUTS')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
    context.close()

def test_ui_refuses_unlabelled_payload(app):
    from playwright.sync_api import expect
    browser,url=app;context=browser.new_context();page=context.new_page()
    def unlabel(route):
        response=route.fetch();body=response.json();body['evidence_header'].pop('stage')
        route.fulfill(response=response,body=json.dumps(body))
    page.route('**/api/runs/*',unlabel);page.goto(url)
    expect(page.locator('#content')).to_contain_text('Missing evidence_header.stage')
    assert page.locator('#time-scrubber').count()==0
    context.close()
