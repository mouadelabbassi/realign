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
from test_auto_live import auto_factory

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
    page.wait_for_function('async()=>{const s=await(await fetch("/api/status")).json();return s.capture.frames>=5;}')
    page.get_by_role('button', name='Stop and analyze', exact=True).click()
    expect(page.locator('#recordings')).to_contain_text('BLOCKED_INPUTS')
    expect(page.locator('#recordings')).to_contain_text('MATCHING_REAL_SAM_RECEIPT_REQUIRED')
    video=page.locator('video'); video.evaluate('(v)=>v.load()')
    page.wait_for_function('()=>document.querySelector("video").readyState>=2')
    page.get_by_role('button', name='Disconnect', exact=True).click()
    expect(page.locator('#camera-state')).to_have_text('IDLE')
    page.locator('.library-panel > summary').click()
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


def test_authorized_concurrent_investigation_and_stop_keeps_recording(lab_ui):
    """TEST_FIXTURE camera + mocked Meta + official SAM parser, no remote calls."""
    from playwright.sync_api import expect
    from test_live_investigation import ScriptedAdapter
    from test_auto_live import AutoMeta
    from realign.physical.live_investigation import LiveInvestigation
    from realign.physical.live_science import LiveScientificSession
    from realign.perception.sam_client import SamClient
    browser, controller, urls, tmp = lab_ui
    transport = AutoMeta()
    holder = {}
    class Client(SamClient):
        async def segment_video(self, path, metadata):
            transport.frame_count = len(metadata.pts)
            return await super().segment_video(path, metadata)
    def factory(root, policy, **kwargs):
        def client():
            return Client(transport, source='SIMULATED_API_FIXTURE', before_request=holder['live'].ledger.reserve, concept=holder['live'].config.target_prompt)
        live = LiveInvestigation(root, policy, source='TEST_FIXTURE', sam_factory=client,
            reasoner_factory=lambda owner: LiveScientificSession(owner, adapter_factory=ScriptedAdapter), **kwargs)
        holder['live'] = live
        return live
    controller.live_factory = factory
    context = browser.new_context(viewport={'width': 1200, 'height': 950})
    context.route('**/*', lambda r: r.continue_() if r.request.url.startswith(urls[0] + '/') else r.abort())
    page = context.new_page(); errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(urls[0])
    assert controller.live is None
    page.locator('#authorization').evaluate('(e)=>e.open=true')
    page.locator('#target-prompt').fill('circular test weight'); page.locator('#target-confirmed').check()
    page.locator('#spend-cap').fill('1'); page.locator('#sam-reserve').fill('0.01'); page.locator('#muse-reserve').fill('0.02')
    page.locator('#ai-consent').check()
    page.locator('#ai-start').click()
    expect(page.locator('#ai-state')).to_contain_text('TEST_FIXTURE')
    expect(page.locator('#camera-state')).to_have_text('RECORDING')
    page.wait_for_function('async()=>{const s=await(await fetch("/api/status")).json();return s.investigation?.processed_windows>=1;}', timeout=30000, polling=250)
    expect(page.locator('#sam-overlay')).to_be_visible(timeout=15000)
    assert transport.requests[0]['input'][0]['content'][1]['type']=='input_image'
    assert page.locator('#ai-reason').count()==0
    expect(page.locator('#pending-action')).to_be_visible(timeout=15000)
    expect(page.locator('#action-text')).to_contain_text('STATIONARY_REFERENCE')
    page.locator('#confirm-action').click()
    expect(page.locator('#action-text')).to_contain_text('Human intent confirmed')
    shots = Path(os.environ.get('REALIGN_SCREENSHOT_DIR', str(tmp / 'screenshots'))); shots.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(shots / 'live_investigation_TEST_FIXTURE.png'), full_page=True)
    page.locator('#ai-stop').click()
    expect(page.locator('#ai-state')).to_contain_text('STOPPED')
    expect(page.locator('#camera-state')).to_have_text('RECORDING')
    count = controller.live.ledger.snapshot()['total_requests']
    page.wait_for_timeout(500)
    assert controller.live.ledger.snapshot()['total_requests'] == count
    assert not errors
    page.get_by_role('button', name='Stop and analyze', exact=True).click()
    context.close()


def test_empty_masks_show_local_readiness_and_never_invoke_muse(lab_ui):
    """TEST_FIXTURE empty SAM stream, no Meta transport or physical camera."""
    from playwright.sync_api import expect
    from test_live_investigation import MockMeta, MockStream, ScriptedAdapter
    from realign.synth.video_fixture import fixture_events
    from realign.physical.live_investigation import LiveInvestigation
    from realign.physical.live_science import LiveScientificSession
    from realign.perception.sam_client import SamClient
    browser, controller, urls, tmp = lab_ui
    transport=MockMeta();holder={}
    async def empty(**kwargs): return MockStream(fixture_events(frames=[]),transport)
    transport.responses.create=empty
    def factory(root,policy,**kwargs):
        def client(): return SamClient(transport,source='SIMULATED_API_FIXTURE',
            concept=holder['live'].config.target_prompt,before_request=holder['live'].ledger.reserve)
        live=LiveInvestigation(root,policy,source='TEST_FIXTURE',sam_factory=client,
            reasoner_factory=lambda owner:LiveScientificSession(owner,adapter_factory=ScriptedAdapter),**kwargs)
        holder['live']=live;return live
    controller.live_factory=factory
    page=browser.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.route('**/*',lambda route:route.continue_() if route.request.url.startswith(urls[0]+'/') else route.abort())
    page.goto(urls[0]);page.locator('#connect').click();page.locator('#start').click()
    page.locator('#authorization').evaluate('(e)=>e.open=true')
    page.locator('#target-prompt').fill('grey test weight');page.locator('#target-confirmed').check()
    page.locator('#spend-cap').fill('1');page.locator('#sam-reserve').fill('0.01');page.locator('#muse-reserve').fill('0.02');page.locator('#ai-consent').check()
    page.locator('#ai-start').click()
    expect(page.locator('#detection-guidance')).to_contain_text('SAM_NO_MASKS',timeout=30000)
    expect(page.locator('#ai-detection')).to_contain_text('0 masks returned')
    expect(page.locator('#target-identity')).to_contain_text('NO_TARGET_OBSERVED')
    before=len(controller.arrivals)
    page.wait_for_function('(n)=>fetch("/api/status").then(r=>r.json()).then(s=>s.capture.frames>n+5)',arg=before)
    assert page.locator('#ai-reason').count()==0
    expect(page.locator('#readiness-text')).to_contain_text('NO_USABLE_OBSERVATIONS')
    assert controller.live.ledger.snapshot()['attempted_requests']['muse']==0
    assert controller.live.pending_action is None
    expect(page.locator('#camera-state')).to_have_text('RECORDING')
    shots=Path(os.environ.get('REALIGN_SCREENSHOT_DIR',str(tmp/'screenshots')));shots.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(shots/'live_empty_TEST_FIXTURE.png'),full_page=True)
    page.locator('#ai-stop').click();page.locator('#stop').click()
    assert not errors
    page.close()


def test_auto_live_partial_masks_slow_muse_checkpoint_and_independent_controls(lab_ui,auto_factory):
    from playwright.sync_api import expect
    from test_auto_live import AutoMeta
    from test_live_investigation import ScriptedAdapter
    entered,release=threading.Event(),threading.Event()
    class SlowMuse(ScriptedAdapter):
        def next(self,context):
            reply=super().next(context)
            entered.set();release.wait(timeout=15)
            return reply
    browser,controller,urls,tmp=lab_ui
    factory,transport,_=auto_factory(AutoMeta(partial_hold=True),adapter_factory=SlowMuse)
    controller.live_factory=factory
    page=browser.new_page(viewport={'width':1440,'height':1050})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.route('**/*',lambda route:route.continue_() if route.request.url.startswith(urls[0]+'/') else route.abort())
    page.goto(urls[0]);page.locator('#open-authorization').click()
    expect(page.locator('.spark-symbol')).to_have_text('✳')
    for selector,value in [('target-prompt','circular test weight'),('spend-cap','1'),('sam-reserve','0.01'),('muse-reserve','0.02')]:page.locator('#'+selector).fill(value)
    page.locator('#target-confirmed').check();page.locator('#ai-consent').check();page.locator('#ai-start').click()
    expect(page.locator('#camera-state')).to_have_text('RECORDING')
    expect(page.locator('#sam-overlay')).to_be_visible(timeout=15000)
    expect(page.locator('#tracking-label')).to_contain_text('partial stream')
    assert not controller.live.trajectory
    before=len(controller.arrivals)
    page.wait_for_function('(n)=>fetch("/api/status").then(r=>r.json()).then(s=>s.capture.frames>n+10)',arg=before)
    assert controller.live.ledger.snapshot()['attempted_requests']['muse']==0
    transport.partial_hold.clear()
    assert entered.wait(timeout=15)
    before=len(controller.arrivals)
    page.wait_for_function('(n)=>fetch("/api/status").then(r=>r.json()).then(s=>s.capture.frames>n+10)',arg=before)
    release.set()
    expect(page.locator('#pending-action')).to_be_visible(timeout=15000)
    pending=controller.live.pending_action['request_id'];hypotheses=controller.live.scientific['hypotheses'][:]
    before=len(controller.arrivals)
    page.wait_for_function('(n)=>fetch("/api/status").then(r=>r.json()).then(s=>s.capture.frames>n+10)',arg=before)
    assert controller.live.pending_action['request_id']==pending and controller.live.scientific['hypotheses']==hypotheses
    assert page.locator('#ai-reason').count()==0
    page.locator('#ai-pause').click();expect(page.locator('#ai-state')).to_contain_text('PAUSED')
    count=controller.live.ledger.snapshot()['total_requests']
    before=len(controller.arrivals)
    page.wait_for_function('(n)=>fetch("/api/status").then(r=>r.json()).then(s=>s.capture.frames>n+10)',arg=before)
    assert controller.live.ledger.snapshot()['total_requests']==count
    page.locator('#ai-resume').click();expect(page.locator('#ai-state')).to_contain_text('PENDING_PHYSICAL_ACTION')
    shots=Path(os.environ.get('REALIGN_SCREENSHOT_DIR',str(tmp/'screenshots')));shots.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(shots/'auto_live_TEST_FIXTURE_desktop.png'),full_page=True)
    page.screenshot(path=str(shots/'auto_live_TEST_FIXTURE_preview.png'))
    page.set_viewport_size({'width':390,'height':844})
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(path=str(shots/'auto_live_TEST_FIXTURE_mobile.png'),full_page=True)
    page.locator('#ai-stop').click();expect(page.locator('#ai-state')).to_contain_text('STOPPED')
    count=controller.live.ledger.snapshot()['total_requests'];before=len(controller.arrivals)
    page.wait_for_function('(n)=>fetch("/api/status").then(r=>r.json()).then(s=>s.capture.frames>n+10)',arg=before)
    assert controller.live.ledger.snapshot()['total_requests']==count
    assert not errors
    page.locator('#stop').click();page.close()


def test_unauthorized_camera_connection_cannot_dispatch_meta(lab_ui,auto_factory):
    from playwright.sync_api import expect
    browser,controller,urls,tmp=lab_ui
    factory,transport,_=auto_factory();controller.live_factory=factory
    page=browser.new_page();page.goto(urls[0]);page.locator('#connect').click()
    expect(page.locator('#camera-state')).to_have_text('CAMERA_CONNECTED')
    page.locator('#start').click()
    page.wait_for_function('()=>fetch("/api/status").then(r=>r.json()).then(s=>s.capture.frames>10)')
    assert controller.live is None and not transport.dispatches
    page.locator('#stop').click();page.close()


def test_scientific_markdown_and_math_are_safe_in_both_workspaces(lab_ui):
    from playwright.sync_api import expect
    browser,controller,urls,tmp=lab_ui
    source=r'''# Observation **review**

Paragraph with *emphasis*, ~~discarded text~~, `inline code`, and $x^2$.

> A source-backed quote.

1. First observation
2. Second observation

- [x] Timing reviewed
- [ ] Geometry missing

| Quantity | Unit |
| --- | --- |
| Position | px |

```python
print("<source>")
```

$$\theta(t) = \sin(t)$$

\(a+b\) and [reference](https://example.com/evidence).

<img src=x onerror="window.markdownPwned=1"><script>window.markdownPwned=1</script>
[unsafe](javascript:alert(1))
'''
    for url,selector in [(urls[0],'#science-status'),(urls[1],'#content')]:
        page=browser.new_page(viewport={'width':1000,'height':950});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(url);page.wait_for_function('()=>Boolean(window.RealignMarkdown)')
        if selector=='#content':page.wait_for_selector('#time-scrubber')
        page.evaluate('([selector,text])=>RealignMarkdown.render(document.querySelector(selector),text)',[selector,source])
        root=page.locator(selector)
        expect(root.locator('h1 strong')).to_have_text('review')
        expect(root.locator('table')).to_contain_text('Position')
        expect(root.locator('blockquote')).to_contain_text('source-backed')
        expect(root.locator('pre code')).to_contain_text('print("<source>")')
        assert root.locator('.katex').count()==3
        assert root.locator('script,img,iframe').count()==0
        assert root.locator('a[href^="javascript:"]').count()==0
        assert page.evaluate('window.markdownPwned===undefined')
        assert root.locator('a[href="https://example.com/evidence"]').get_attribute('rel')=='noopener noreferrer'
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        assert not errors
        page.close()


def test_find_cameras_shows_search_results_and_no_device_guidance(lab_ui):
    from playwright.sync_api import expect
    browser,controller,urls,tmp=lab_ui
    available={2,5}
    class Probe(InjectedCamera):
        def __init__(self,index):self.index=index
        def isOpened(self):return self.index in available
    controller.camera_factory=lambda index,*args:Probe(index)
    original=controller.enumerate_devices
    def slower(maximum=8):time.sleep(.3);return original(maximum)
    controller.enumerate_devices=slower
    page=browser.new_page(viewport={'width':390,'height':844});page.goto(urls[0])
    button=page.get_by_role('button',name='Find cameras',exact=True)
    expect(button).to_be_visible();button.click()
    expect(page.locator('#camera-discovery')).to_contain_text('Searching camera inputs')
    expect(page.locator('#camera-discovery')).to_contain_text('2 cameras found')
    assert page.locator('#devices option').all_text_contents()==['Camera 2 · INJECTED_BROWSER_FIXTURE','Camera 5 · INJECTED_BROWSER_FIXTURE']
    page.locator('#connect').click()
    expect(page.locator('#camera-state')).to_have_text('CAMERA_CONNECTED')
    assert controller.device['index']==2
    expect(button).to_be_disabled()
    page.locator('#disconnect').click();available.clear()
    button.click();expect(page.locator('#camera-discovery')).to_contain_text('No cameras found')
    expect(page.locator('#camera-discovery')).to_contain_text('Windows camera permissions')
    expect(page.locator('#connect')).to_be_disabled()
    assert controller.live is None and controller.snapshot()['new_meta_calls']==0
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.close()
