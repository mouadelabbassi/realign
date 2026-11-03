"""Opt-in browser tests. All moving frames are explicitly injected test fixtures."""
import os
from pathlib import Path
import threading
import time
import numpy as np
import pytest

from realign.physical.live_lab import LabLibrary, CaptureController
from realign.physical.lab_server import make_lab_server
from realign.product.server import make_server

pytestmark = pytest.mark.skipif(os.environ.get('REALIGN_BROWSER_TESTS') != '1', reason='Opt-in local browser test')
ROOT = Path(__file__).resolve().parents[1]


class InjectedCamera:
    def isOpened(self): return True
    def getBackendName(self): return 'INJECTED_BROWSER_FIXTURE'
    def set(self, *args): return True
    def get(self, *args): return 30.
    def release(self): pass
    def read(self):
        time.sleep(.02)
        return True, np.full((64, 96, 3), 80, dtype=np.uint8)


@pytest.fixture
def lab_ui(tmp_path):
    from playwright.sync_api import sync_playwright
    controller = CaptureController(LabLibrary(tmp_path / 'library'), camera_factory=lambda *args: InjectedCamera())
    servers = [make_lab_server(controller, port=0), make_server(ROOT / 'artifacts/task05/demo', port=0, lab_root=controller.library.root)]
    threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in servers]
    for t in threads: t.start()
    with sync_playwright() as p:
        options = {'headless': True, 'env': {k:v for k,v in os.environ.items() if k != 'MODEL_API_KEY'}}
        if os.environ.get('REALIGN_BROWSER_EXECUTABLE'): options['executable_path'] = os.environ['REALIGN_BROWSER_EXECUTABLE']
        browser = p.chromium.launch(**options)
        yield browser, controller, [f'http://127.0.0.1:{s.server_port}' for s in servers], tmp_path
        browser.close()
    for s in servers: s.shutdown(); s.server_close()
    for t in threads: t.join(timeout=5)
    controller.close()


def test_preview_record_stop_and_pilot_admission(lab_ui):
    from playwright.sync_api import expect
    browser, controller, urls, tmp = lab_ui
    context = browser.new_context(viewport={'width': 1200, 'height': 950})
    context.route('**/*', lambda r: r.continue_() if any(r.request.url.startswith(url + '/') for url in urls) else r.abort())
    page = context.new_page(); errors=[]; page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(urls[0])
    page.get_by_role('button', name='Connect', exact=True).click()
    expect(page.locator('#camera-state')).to_have_text('CAMERA_CONNECTED')
    expect(page.locator('#preview')).to_be_visible()
    page.wait_for_function('()=>document.querySelector("#preview").naturalWidth > 0')
    page.get_by_role('button', name='Start recording', exact=True).click()
    expect(page.locator('#camera-state')).to_have_text('RECORDING')
    expect(page.locator('#telemetry')).to_contain_text('recorded frames')
    # Wait for actual encoded frames rather than a fixed browser delay.
    page.wait_for_function('async()=>{const s=await(await fetch("/api/status")).json();return s.capture.frames>=5;}')
    page.get_by_role('button', name='Stop and analyze', exact=True).click()
    expect(page.locator('#recordings')).to_contain_text('BLOCKED_INPUTS')
    expect(page.locator('#recordings')).to_contain_text('MATCHING_REAL_SAM_RECEIPT_REQUIRED')
    video=page.locator('video'); video.evaluate('(v)=>v.load()')
    page.wait_for_function('()=>document.querySelector("video").readyState>=2')
    page.get_by_role('button', name='Disconnect', exact=True).click()
    expect(page.locator('#camera-state')).to_have_text('IDLE')
    pilot=tmp/'WhatsApp-pilot.mp4'; pilot.write_bytes(b'not calibrated')
    page.locator('#path').fill(str(pilot));page.get_by_role('button',name='Import and analyze locally').click()
    expect(page.locator('#recordings')).to_contain_text('UNREADABLE_CONTAINER')
    shots=Path(os.environ.get('REALIGN_SCREENSHOT_DIR',str(tmp/'screenshots')));shots.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(shots/'live_lab_fixture_desktop.png'),full_page=True)
    assert not errors
    context.close()


def test_phone_views_show_actual_local_blockers_and_keep_replay_available(lab_ui):
    from playwright.sync_api import expect
    browser, controller, urls, tmp = lab_ui
    pilot=tmp/'pilot.mp4';pilot.write_bytes(b'bad media');controller.library.import_video(pilot)
    context=browser.new_context(viewport={'width':390,'height':844})
    context.route('**/*',lambda r:r.continue_() if r.request.url.startswith(urls[1]+'/') else r.abort())
    page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(urls[1]);page.wait_for_selector('#time-scrubber')
    page.locator('[data-source="phone"]').click()
    expect(page.locator('#content')).to_contain_text('Live Physical Lab')
    expect(page.locator('#content')).to_contain_text('PILOT_NOT_A_CONTROLLED_EXPERIMENT')
    for view in ['investigation','experiment','decision','evidence']:
        page.locator(f'[data-view="{view}"]').click()
        expect(page.locator('#content')).to_contain_text('Live Physical Lab')
    expect(page.locator('#content')).to_contain_text('Independent physical evaluation')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.locator('[data-source="synthetic"]').click()
    page.locator('[data-view="reality"]').click()
    expect(page.locator('#time-scrubber')).to_be_visible()
    assert not errors
    context.close()
