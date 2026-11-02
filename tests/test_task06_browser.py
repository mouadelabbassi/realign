"""Opt-in local UI tests. Automated clicks never become real measurement references."""
import json,os,threading
from pathlib import Path
import pytest
from realign.product.server import make_server

ROOT=Path(__file__).resolve().parents[1]
SHOTS=Path(os.environ.get('REALIGN_SCREENSHOT_DIR',str(ROOT/'artifacts/task06/screenshots')))
pytestmark=pytest.mark.skipif(os.environ.get('REALIGN_BROWSER_TESTS')!='1',reason='Opt-in isolated browser regression')


@pytest.fixture(scope='module')
def browser_app():
    from playwright.sync_api import sync_playwright
    server=make_server(ROOT/'artifacts/task05/demo',port=0,closure_root=ROOT/'artifacts/task06')
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    with sync_playwright() as p:
        args={'headless':True,'env':{k:v for k,v in os.environ.items() if k!='MODEL_API_KEY'}}
        if os.environ.get('REALIGN_BROWSER_EXECUTABLE'):args['executable_path']=os.environ['REALIGN_BROWSER_EXECUTABLE']
        browser=p.chromium.launch(**args)
        yield browser,'http://127.0.0.1:'+str(server.server_port)
        browser.close()
    server.shutdown();server.server_close();thread.join(timeout=5)


def page_for(app):
    browser,url=app;c=browser.new_context(viewport={'width':1440,'height':1050})
    c.route('**/*',lambda r:r.continue_() if r.request.url.startswith(url+'/') or r.request.url.startswith('blob:') else r.abort())
    page=c.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(url);page.wait_for_selector('#time-scrubber')
    return c,page,errors


def test_annotation_page_is_clean_interactive_and_exports_only_supplied_centers(browser_app,tmp_path):
    from playwright.sync_api import expect
    c,page,errors=page_for(browser_app)
    page.locator('[data-source="external"]').click()
    expect(page.locator('#content')).to_contain_text('NOT VALIDATED')
    expect(page.locator('#content')).to_contain_text('38 rejected')
    with page.expect_popup() as popup:
        page.get_by_role('link',name='Open independent clean-frame annotation').click()
    review=popup.value;review.on('pageerror',lambda e:errors.append(str(e)))
    expect(review.locator('#frame-description')).to_contain_text('frame 157')
    review.wait_for_function('()=>document.querySelector("canvas").width===1280')
    expect(review.locator('#coordinate')).to_have_text('No center placed.')
    shots=SHOTS;shots.mkdir(parents=True,exist_ok=True)
    review.screenshot(path=str(shots/'clean_annotation_interface.png'),full_page=True)
    # UI protocol exercise only: the arbitrary click is explicitly cleared and
    # no fabricated reference center is saved or passed to an accuracy scorer.
    review.locator('#image').click(position={'x':40,'y':40})
    review.locator('#sigma').fill('1.25')
    expect(review.locator('#progress')).to_have_text('1 / 20 centers placed')
    review.locator('#next').click();review.locator('#previous').click()
    expect(review.locator('#sigma')).to_have_value('1.25')
    review.locator('#clear').click()
    expect(review.locator('#progress')).to_have_text('0 / 20 centers placed')
    review.locator('#reviewer').fill('AUTOMATED_UI_TEST_ONLY_NO_REFERENCES')
    review.locator('#download').click()
    expect(review.locator('#status')).to_contain_text('Confirm independent annotation')
    review.locator('#independent').check()
    with review.expect_download() as download:review.locator('#download').click()
    target=tmp_path/'EMPTY_UI_PROTOCOL_EXPORT.json';download.value.save_as(target)
    document=json.loads(target.read_text());assert all(row['center_px'] is None for row in document['rows'])
    assert document['rows'][0]['frame_index']==157
    assert not errors
    c.close()


def test_phone_blockers_and_synthetic_independent_evidence_are_explicit(browser_app):
    from playwright.sync_api import expect
    c,page,errors=page_for(browser_app)
    page.locator('[data-source="phone"]').click()
    expect(page.locator('#content')).to_contain_text('BLOCKED INPUTS')
    expect(page.locator('#content')).to_contain_text('MEASURED_CALIBRATION_NOT_SUPPLIED')
    expect(page.locator('#content')).to_contain_text('No physical experiment has been requested')
    page.locator('[data-view="evidence"]').click()
    expect(page.locator('#content')).to_contain_text('Separate precommitted dataset and model')
    independent=json.loads((ROOT/'artifacts/task06/g5_demo/validation.json').read_text())
    expect(page.locator('#content')).to_contain_text((independent.get('independent_verdict') or independent['status']).replace('_',' '))
    expect(page.locator('#content')).to_contain_text('Peg-position error')
    expect(page.locator('#content')).to_contain_text('Peg-position tolerance')
    page.locator('#run-select').select_option('live-02')
    expect(page.locator('#content')).to_contain_text('Actual Muse reasoning contribution')
    expect(page.locator('#content')).to_contain_text('same predictive error')
    shots=SHOTS;shots.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(shots/'independent_evidence.png'),full_page=True)
    assert not errors
    c.close()
