"""Deterministic rendered MP4 and SIMULATED SAM protocol events.

No API is called. The circle payload encodes our own 17x17 binary disk, generated
once with meta-sam-parser 0.1.0's test codec. Runtime uses public parser APIs only.
This module is outside the real perception/inference path.
"""
from pathlib import Path
import subprocess
import numpy as np
from realign.physics import PendulumParams,simulate
from realign.perception.video import probe_video
from realign.perception.calibration import fit_planar_calibration
from realign.observation.camera import project

CIRCLE_PAYLOAD="!!!!!=H:TBY.QyLJY4s)mxhmgx'_n)R@smfO"


def protocol_line(frame,left,top,*,width=640,height=480,object_id='0'):
    return (f'<{frame}f>{object_id}<|box;x1={left};y1={top};x2={left+16};y2={top+16};w={width};h={height}|>'
            f'<|mask;x=0;y=0;data=17,17,{CIRCLE_PAYLOAD}|>\n')


def fixture_events(*,frames=None,text=None,failure=None):
    if text is None:
        frames=[0,2] if frames is None else frames
        text=''.join(protocol_line(f,100,150) for f in frames)
    if failure=='malformed':
        text=text.replace(CIRCLE_PAYLOAD,'!invalid')
    if failure=='frame_mismatch':
        text=text.replace('<0f>','<9999f>')
    lane={'item_id':'msg_SIMULATED_FIXTURE','output_index':0,'content_index':0}
    events=[dict(lane,type='response.output_text.delta',delta=text)]
    if failure=='eof':
        return events
    if failure=='refusal':
        return [dict(lane,type='response.refusal.delta',delta='simulated refusal')]
    events.append(dict(lane,type='response.content_part.done',part={'type':'output_text','text':text}))
    status='incomplete' if failure=='incomplete' else 'failed' if failure=='failed' else 'completed'
    response={'id':'resp_SIMULATED_FIXTURE','status':status}
    if status=='incomplete':
        response['incomplete_details']={'reason':'max_output_tokens'}
    if status=='failed':
        response['error']={'code':'SIMULATED_FAILURE','message':'fixture failure, not an API call'}
    events.append({'type':'response.'+status,'response':response})
    return events


def fixture_calibration():
    board=np.array([[-.5,.05],[.5,.05],[.5,-.75],[-.5,-.75],[-.4,-.35],[.4,-.35]])
    checks=np.array([[-.2,-.2],[.2,-.2],[-.2,-.6],[.2,-.6]])
    image=board*[500.,-500.]+[320.,80.]
    check_image=checks*[500.,-500.]+[320.,80.]
    return fit_planar_calibration(board,image,pivot_px=(320.,80.),hanging_px=(320.,440.),
        image_size=(640,480),calibration_id='SYNTHETIC_FIXTURE_CALIBRATION',source='SYNTHETIC_FIXTURE',
        check_board_xy_m=checks,check_image_xy_px=check_image)


def render_fixture(path,*,duration_s=3.,angle_rad=.45,release_s=.4,stationary=False,variable_rate=False):
    import cv2
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    indices=np.arange(int(round(duration_s*25))+1)
    times=(np.where(indices<10,indices,10+2*(indices-10)) if variable_rate else indices)/25.
    params=PendulumParams(.72,gamma_per_s=.06,quadratic_drag_per_m=.02)
    relative=times-release_s
    xy=np.tile(params.length_m*np.array([np.sin(angle_rad),-np.cos(angle_rad)]),(len(times),1))
    if not stationary:
        post=relative>=0.
        grid=np.unique(np.r_[0.,relative[post]])
        if len(grid)>1:
            result=simulate(params,angle_rad,0.,grid)
            xy[post]=result.xy_m[np.searchsorted(grid,relative[post])]
    reference=project(xy,fixture_calibration())
    centers=np.rint(reference).astype(int)
    command=['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s','640x480','-r','25',
             '-i','pipe:0','-an']
    if variable_rate:
        command+=['-vf',"setpts='if(lt(N,10),N,10+2*(N-10))/(25*TB)'",'-fps_mode','vfr']
    command+=['-c:v','libx264','-preset','veryfast','-crf','18','-threads','1','-pix_fmt','yuv420p',str(path)]
    process=subprocess.Popen(command,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        for center in centers:
            frame=np.zeros((480,640,3),np.uint8)
            cv2.circle(frame,tuple(center),8,(255,255,255),-1)
            process.stdin.write(frame.tobytes())
        process.stdin.close()
        process.wait(timeout=60)
        if process.returncode:
            raise RuntimeError('synthetic fixture FFmpeg encoding failed')
    finally:
        if process.poll() is None:
            process.kill()
        if process.stderr:
            process.stderr.close()
    metadata=probe_video(path,source_kind='SYNTHETIC_RENDER')
    if len(metadata.pts)!=len(times) or not np.allclose(metadata.t_s,times,atol=1e-8):
        raise RuntimeError('rendered fixture PTS do not match intended presentation times')
    # Two intentional SAM dropouts exercise missing-mask handling (not decoded-frame loss).
    missing=set() if stationary else {13,37}
    text=''.join(protocol_line(i,int(c[0]-8),int(c[1]-8)) for i,c in enumerate(centers) if i not in missing)
    return {'path':path,'metadata':metadata,'events':fixture_events(text=text),
            'reference_px':reference,'rendered_centers_px':centers,'release_s':release_s,
            'scope':'SYNTHETIC_RENDER + SIMULATED_API_FIXTURE; not SAM output'}
