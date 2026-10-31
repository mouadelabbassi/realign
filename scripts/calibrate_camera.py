"""Fit measured planar correspondences or checkerboard intrinsics from JSON."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from realign.perception.calibration import fit_planar_calibration,calibrate_lens


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input_json',type=Path)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--lens',action='store_true',help='input has object_points_m, image_points_px and image_size for >=5 checkerboard views')
    args=p.parse_args()
    data=json.loads(args.input_json.read_text(encoding='utf-8'))
    result=calibrate_lens(**data) if args.lens else asdict(fit_planar_calibration(**data))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('Calibration written:',args.output)
    print('Evidence source:',data.get('source','checkerboard inputs; verify provenance separately'))


if __name__=='__main__':
    main()
