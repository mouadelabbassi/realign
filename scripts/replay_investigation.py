"""Re-execute recorded synthetic actions with fresh isolated numerical tools."""
from realign.investigator_platform import delegate
delegate('replay_investigation.py')
import argparse
import json
from pathlib import Path
from realign.agent.adapters import ReplayAdapter
from realign.report.investigator_run import execute, load_gate, write_run, format_summary, ROOT

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('trace',type=Path)
    p.add_argument('--gate',type=Path,default=Path('artifacts/task04/null_calibration.json'))
    p.add_argument('--uncalibrated',action='store_true')
    p.add_argument('--output',type=Path,default=Path('artifacts/task04/replay.json'))
    args=p.parse_args(); trace_path=args.trace.resolve()
    if not trace_path.is_relative_to((ROOT/'artifacts/task04').resolve()):
        raise SystemExit('trace must be in the approved task04 evidence directory')
    trace=json.loads(trace_path.read_text(encoding='utf-8'))
    f=trace['fixture_provenance']
    gate=None if args.uncalibrated else load_gate(args.gate)
    result=execute(f['label_post_freeze_only'],gate=gate,seed=f['seed'],sigma=f['noise_sd_px'],adapter=ReplayAdapter(trace))
    write_run(args.output,result); print(format_summary(result))
