"""Opt-in local application browser tests. No API, personal profile or fitting.

REALIGN_BROWSER_TESTS=1 python -m pytest -q tests/test_product_browser.py
Install .[ui-test] and `python -m playwright install chromium` first. Optionally
set REALIGN_BROWSER_EXECUTABLE to an installed Chrome/Edge binary.
"""
import os
from pathlib import Path
import threading
import pytest
from realign.product.server import make_server

ROOT=Path(__file__).resolve().parents[1]
SHOTS=Path(os.environ.get('REALIGN_SCREENSHOT_DIR',str(ROOT/'artifacts/task05/screenshots')))
pytestmark=pytest.mark.skipif(os.environ.get('REALIGN_BROWSER_TESTS')!='1',reason='Opt-in browser integration; no API credentials needed')


@pytest.fixture(scope='module')
def ui():
    from playwright.sync_api import sync_playwright
    media=ROOT/'data/raw/external/blocked-pendulum.mp4'
    server=make_server(ROOT/'artifacts/task05/demo',port=0,
                       media={'external.mp4':media} if media.exists() else None)
    thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    with sync_playwright() as p:
        options={'headless':True,'env':{k:v for k,v in os.environ.items() if k!='MODEL_API_KEY'}}
        if os.environ.get('REALIGN_BROWSER_EXECUTABLE'):
            options['executable_path']=os.environ['REALIGN_BROWSER_EXECUTABLE']
        browser=p.chromium.launch(**options)
        yield browser,'http://127.0.0.1:'+str(server.server_port)
        browser.close()
    server.shutdown(); server.server_close(); thread.join(timeout=5)


def open_page(ui,*,mobile=False):
    browser,url=ui
    context=browser.new_context(viewport={'width':390,'height':844} if mobile else {'width':1440,'height':1050})
    context.route('**/*',lambda route:route.continue_() if route.request.url.startswith(url+'/') else route.abort())
    page=context.new_page(); errors=[]; page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(url); page.wait_for_selector('#time-scrubber')
    return context,page,errors


def test_five_views_two_rounds_playback_and_frozen_evaluation(ui):
    from playwright.sync_api import expect
    context,page,errors=open_page(ui)
    page.get_by_role('button',name='Round 2',exact=True).click()
    expect(page.locator('.round-button.active')).to_have_text('Round 2')
    page.locator('#time-scrubber').fill('20')
    assert '0.00 /' not in page.locator('#timeline-label').inner_text()
    page.get_by_role('button',name='Post-freeze evaluation',exact=True).click()
    expect(page.locator('#content')).to_contain_text('DEVELOPMENT')
    shots=SHOTS; shots.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(shots/'reality_desktop.png'),full_page=True)
    for view,title in [('investigation','Investigation'),('experiment','Experiment Loop'),('decision','Model Decision'),('evidence','Evidence')]:
        page.locator('[data-view="'+view+'"]').click()
        expect(page.locator('#page-title')).to_have_text(title)
        assert len(page.locator('#content').inner_text())>150
    expect(page.locator('#content')).to_contain_text('POST-FREEZE DEVELOPMENT')
    page.screenshot(path=str(shots/'evidence_desktop.png'),full_page=True)
    assert not errors
    context.close()


def test_live_trace_failure_and_measurement_semantics(ui):
    from playwright.sync_api import expect
    context,page,errors=open_page(ui)
    ids=page.locator('#run-select option').evaluate_all('(nodes)=>nodes.map(n=>n.value)')
    if 'live-02' in ids:
        page.locator('#run-select').select_option('live-02')
        expect(page.locator('#run-provenance')).to_contain_text('LIVE MUSE')
        page.locator('[data-view="experiment"]').click()
        page.get_by_role('button',name='Inspect the updated round',exact=False).click()
        expect(page.locator('#content')).to_contain_text('Round 2')
    if 'live-01' in ids:
        with page.expect_response('**/api/runs/live-01'):
            page.locator('#run-select').select_option('live-01')
        expect(page.locator('#content')).to_have_attribute('aria-busy','false')
        page.locator('[data-view="decision"]').click()
        expect(page.locator('#content')).to_contain_text('Abstain')
    with page.expect_response('**/api/runs/det-measurement'):
        page.locator('#run-select').select_option('det-measurement')
    expect(page.locator('#content')).to_have_attribute('aria-busy','false')
    expect(page.locator('#run-select')).to_have_value('det-measurement')
    page.locator('[data-view="decision"]').click()
    expect(page.locator('#content')).to_contain_text('Measurement correction required')
    expect(page.locator('#content')).to_contain_text('Measurement correction applied: no. Correction verified: no.')
    assert not errors
    context.close()


def test_external_and_phone_remain_separate_responsive_sources(ui):
    from playwright.sync_api import expect
    context,page,errors=open_page(ui,mobile=True)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    shots=SHOTS; shots.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(shots/'reality_mobile.png'),full_page=True)
    page.locator('[data-source="external"]').click()
    expect(page.locator('#page-title')).to_have_text('External Video')
    expect(page.locator('#content')).to_contain_text('REAL EXTERNAL')
    expect(page.locator('#content')).to_contain_text('Unverified')
    expect(page.locator('#run-picker-bar')).to_be_hidden()
    page.screenshot(path=str(shots/'external_mobile.png'),full_page=True)
    page.locator('[data-source="phone"]').click()
    expect(page.locator('#content')).to_contain_text('PHYSICAL VALIDATION PENDING')
    expect(page.locator('#content')).to_contain_text('NOT PROVIDED')
    assert not errors
    context.close()


@pytest.mark.skipif(not (ROOT/'data/raw/external/blocked-pendulum.mp4').is_file(),reason='Optional approved external media is not in Git')
def test_approved_external_media_decodes_and_center_overlay_follows_pts(ui):
    from playwright.sync_api import expect
    context,page,errors=open_page(ui)
    page.locator('[data-source="external"]').click()
    video=page.locator('video')
    expect(video).to_be_visible()
    page.wait_for_function('()=>document.querySelector("video")?.readyState >= 2',timeout=30000)
    video.evaluate('(v)=>{v.pause();v.currentTime=7.033333333333333;}')
    page.wait_for_function('()=>{const v=document.querySelector("video");return v && !v.seeking && v.readyState >= 3;}',timeout=30000)
    page.wait_for_function('()=>document.querySelector(".video-overlay circle") !== null',timeout=15000)
    expect(page.locator('.video-meta')).to_contain_text('Frame 212')
    assert 800<float(page.locator('.video-overlay circle').first.get_attribute('cx'))<900
    page.screenshot(path=str(SHOTS/'external_desktop.png'),full_page=True)
    assert not errors
    context.close()


@pytest.mark.parametrize('body',['{bad','{"status":"COMPLETED"}'])
def test_malformed_backend_fails_visibly_without_substituting_results(ui,body):
    from playwright.sync_api import expect
    context,page,errors=open_page(ui)
    page.route('**/api/runs/*',lambda route:route.fulfill(status=200,content_type='application/json',body=body))
    page.locator('#run-select').select_option('det-nominal')
    expect(page.locator('#content')).to_contain_text('Evidence record unavailable')
    assert page.locator('#time-scrubber').count()==0
    assert not errors
    context.close()
