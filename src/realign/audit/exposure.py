"""Precise sealed-context guard; legitimate peg hypotheses remain allowed."""
import re

PRIVATE_KEYS=frozenset({'nonce_hex','reveal_nonce','hidden_geometry','ground_truth','heldout_observations',
    'sealed_measurements','private_truth','final_holdout_scores','hidden_parameters'})

def assert_public_context(value):
    def visit(x,depth=0):
        if depth>64:raise ValueError('context nesting exceeds approved scope')
        if isinstance(x,dict):
            for key,v in x.items():
                normalized=re.sub(r'(?<!^)(?=[A-Z])','_',str(key)).lower().replace('-','_')
                if normalized in PRIVATE_KEYS:raise ValueError('private sealed-context field refused')
                visit(v,depth+1)
        elif isinstance(x,(list,tuple)):
            for v in x:visit(v,depth+1)
        elif isinstance(x,str) and re.search(r'(?:^|[/\\])(?:sealed|vault|secrets|keys)[/\\]',x,re.I):
            raise ValueError('private filesystem reference refused')
    visit(value)
    return value
