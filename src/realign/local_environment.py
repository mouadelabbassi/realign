"""Explicit local .env bootstrap; SDKs still read MODEL_API_KEY from environment.

Only the user's selected model key is loaded. Nothing is interpolated/executed,
returned, logged or written back. This module is never copied to science workers.
"""
import os
from pathlib import Path
import re
import shlex


def load_model_key(path):
    if os.environ.get('MODEL_API_KEY'):
        return True
    p=Path(path)
    if not p.is_file():
        return False
    if p.stat().st_size>65536:
        raise ValueError('local environment file exceeds size limit')
    values=[]
    for line in p.read_text(encoding='utf-8-sig').splitlines():
        match=re.match(r'^\s*(?:export\s+)?MODEL_API_KEY\s*=\s*(.*)$',line)
        if match:
            try:
                tokens=shlex.split(match[1],comments=True,posix=True)
            except ValueError:
                raise ValueError('invalid local model-key syntax') from None
            if len(tokens)!=1 or not 1<=len(tokens[0])<=4096 or any(c.isspace() for c in tokens[0]):
                raise ValueError('invalid local model-key value')
            values.append(tokens[0])
    if len(values)>1:
        raise ValueError('duplicate local model-key entries')
    if not values:
        return False
    os.environ['MODEL_API_KEY']=values[0]
    return True
