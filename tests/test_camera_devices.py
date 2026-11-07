import sys
import time
from types import SimpleNamespace as NS
import pytest

from realign.physical.camera_devices import windows_cameras
from realign.physical.live_lab import CaptureController, LabLibrary
from test_live_lab import Camera


def catalog(maximum):
    return [{'index':0,'backend_id':700,'backend':'DSHOW','name':'Laptop camera','id':'700:0'},
            {'index':1,'backend_id':1400,'backend':'MSMF','name':'S22 Windows virtual camera','id':'1400:1'}]


def test_named_camera_catalog_preserves_backend_and_does_not_open_devices(tmp_path):
    opened=[]
    def factory(index,backend):opened.append((index,backend));return Camera()
    owner=CaptureController(LabLibrary(tmp_path),camera_factory=factory,camera_catalog=catalog)
    try:
        devices=owner.enumerate_devices()
        assert devices[1]['name']=='S22 Windows virtual camera' and not opened
        owner.connect(1,backend=1400,threaded=False)
        assert opened==[(1,1400)]
        assert owner.device['name']=='S22 Windows virtual camera' and owner.device['backend_id']==1400
        assert owner.snapshot()['preview_size']==[96,64] and owner.snapshot()['new_meta_calls']==0
    finally:owner.close()


def test_usb_portable_device_is_not_fabricated_as_a_camera(tmp_path):
    owner=CaptureController(LabLibrary(tmp_path),camera_factory=lambda *a:Camera(),
        camera_catalog=lambda maximum:catalog(maximum)[:1],
        portable_detector=lambda:[{'name':'S22','kind':'PORTABLE_DEVICE'}])
    devices=owner.enumerate_devices()
    assert [d['name'] for d in devices]==['Laptop camera']
    assert owner.snapshot()['device_scan']['portable_devices'][0]['name']=='S22'
    assert owner.camera is None and owner.live is None


@pytest.mark.parametrize('backend',[True,'1400',-1,9999])
def test_invalid_camera_backends_are_rejected_before_capture(tmp_path,backend):
    owner=CaptureController(LabLibrary(tmp_path),camera_factory=lambda *a:pytest.fail('Capture must not open'))
    with pytest.raises(ValueError,match='backend'):owner.connect(0,backend=backend)
    assert owner.camera is None


def test_windows_catalog_keeps_working_backend_when_the_other_fails(monkeypatch):
    seen=[]
    def enumerate_cameras(backend):
        seen.append(backend)
        if backend==1400:raise RuntimeError('SENSITIVE_DRIVER_RESPONSE')
        return [NS(index=1,name='S22',path='not exposed')]
    monkeypatch.setitem(sys.modules,'cv2_enumerate_cameras',NS(enumerate_cameras=enumerate_cameras))
    devices=windows_cameras()
    assert seen==[700,1400]
    assert devices[0]['index']==1 and devices[0]['backend_id']==700
    assert 'path' not in devices[0]


def test_response_rotation_does_not_treat_local_finalization_as_camera_stall(tmp_path,monkeypatch):
    owner=CaptureController(LabLibrary(tmp_path),camera_factory=lambda *a:Camera())
    owner.connect(0,threaded=False);owner.start()
    for _ in range(3):owner.read_once()
    class Session:
        def confirm_action(self,request):pass
    original=owner.stop
    def slow_finalize(*args,**kwargs):
        result=original(*args,**kwargs);owner.last_frame_ns=time.monotonic_ns()-10_000_000_000;return result
    monkeypatch.setattr(owner,'stop',slow_finalize)
    saved=owner.start
    calls=[]
    def restart(**kwargs):calls.append(kwargs);return saved(**kwargs)
    monkeypatch.setattr(owner,'start',restart)
    owner.live=Session();owner.auto_live=True
    owner.live.root=tmp_path/'TEST_FIXTURE';owner.live.source='TEST_FIXTURE';owner.live.active_action=None
    owner.live.boundary=lambda reason:None;owner.live.record=lambda *args:None
    try:
        owner.confirm_action('TEST_FIXTURE_REQUEST')
        assert calls[0]['_continuation'] is True and owner.writer is not None
        assert owner.arrivals==[]
    finally:
        owner.live=None;owner.auto_live=False;owner.close()


def test_manual_recording_still_rejects_a_stalled_camera(tmp_path):
    owner=CaptureController(LabLibrary(tmp_path),camera_factory=lambda *a:Camera())
    owner.connect(0,threaded=False);owner.last_frame_ns=time.monotonic_ns()-10_000_000_000
    try:
        with pytest.raises(ValueError,match='stalled'):owner.start()
        assert owner.writer is None
    finally:owner.close()
