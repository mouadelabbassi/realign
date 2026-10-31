"""Export original displayed frames and PTS metadata for independent annotation."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from realign.perception.video import probe_video,iter_video_frames


def main():
    import cv2
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('video',type=Path)
    p.add_argument('--output-dir',required=True,type=Path)
    p.add_argument('--frame-index',type=int,action='append',default=[])
    args=p.parse_args()
    metadata=probe_video(args.video,source_kind='REAL_PHONE')
    selected=set(args.frame_index or [0])
    if min(selected)<0 or max(selected)>=len(metadata.pts):
        p.error('requested frame outside original source video')
    args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/'video_metadata.json').write_text(json.dumps(asdict(metadata),indent=2)+'\n',encoding='utf-8')
    for index,frame in enumerate(iter_video_frames(args.video,metadata)):
        if index in selected:
            cv2.imwrite(str(args.output_dir/f'frame_{index:06d}.png'),cv2.cvtColor(frame,cv2.COLOR_RGB2BGR))
    print('Exported',len(selected),'displayed source frames; original integer PTS retained in video_metadata.json')


if __name__=='__main__':
    main()
