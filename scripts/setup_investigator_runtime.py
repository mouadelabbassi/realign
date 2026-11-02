"""Prepare the supported scientific-isolation runtime."""
from realign.investigator_platform import delegate
delegate('setup_investigator_runtime.py')

if __name__=='__main__':
    from realign.tools.sandbox import WorkerClient
    with WorkerClient(timeout_s=90) as worker:
        print('Supported runtime:',worker.isolation,worker.probe)
