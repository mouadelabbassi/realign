from __future__ import annotations
import json
import os
from pathlib import Path
from datetime import datetime, timezone


def main():
    key = os.environ.get('MODEL_API_KEY')
    if not key:
        raise SystemExit('MODEL_API_KEY is not set. Configure it locally; do not commit it.')
    from openai import OpenAI
    client = OpenAI(base_url='https://api.meta.ai/v1',api_key=key,timeout=35)
    model = os.getenv('META_REASONING_MODEL','muse-spark-1.3')
    report={'time_utc':datetime.now(timezone.utc).isoformat(),'model':model,'meta_api_test':'not_run'}
    try:
        result=client.chat.completions.create(model=model,messages=[{'role':'user','content':'Reply with exactly: REALIGN_READY'}])
        report['meta_api_test']='success'
        report['reply']=result.choices[0].message.content
        report['response_id']=result.id
    except Exception as exc:
        report['meta_api_test']='failed'
        report['error_type']=type(exc).__name__
        report['error_message']=str(exc)[:500]
    path=Path('artifacts/meta_smoke.json')
    path.parent.mkdir(exist_ok=True,parents=True)
    path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
    if report['meta_api_test'] != 'success':
        raise SystemExit(1)


if __name__=='__main__': main()
