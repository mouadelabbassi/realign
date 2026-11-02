"""Export portable evidence playback without numerical fitting or API calls."""
from realign.investigator_platform import delegate
delegate('prepare_demo.py')
import argparse
from pathlib import Path
from realign.product.demo import prepare_demo

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,default=Path('artifacts/task05/demo'))
    p.add_argument('--evidence-dir',type=Path,default=Path('artifacts/task05'))
    p.add_argument('--without-mock',action='store_true')
    args=p.parse_args()
    store=prepare_demo(args.output_dir,evidence_dir=args.evidence_dir,include_mock=not args.without_mock,
                       progress=lambda s:print(s,flush=True))
    print('Ready:',len(store.entries),'bound recorded investigations. No fits or API requests.')
