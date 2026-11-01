"""Export handoff schemas only. No tool handlers or agent are implemented."""
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from realign.contracts.investigator_tools import tool_json_schemas

if __name__ == '__main__':
    path = ROOT/'docs/investigator_tool_schemas.json'
    path.write_text(json.dumps(tool_json_schemas(), indent=2, sort_keys=True)+'\n', encoding='utf-8')
    print('Exported five input/output schema pairs:', path)
