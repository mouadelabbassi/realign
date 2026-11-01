"""Small capability probes, not a Muse investigator. Raw replies/errors discarded.

Official contracts: dev.meta.ai/docs/cookbook/structured-output and
dev.meta.ai/docs/cookbook/tool-function-calling. Meta supports tool_choice=auto;
requiring a particular tool is not a documented option.
"""
import json
import math

MODEL = 'muse-spark-1.3'
FORMAT = {'type': 'json_schema', 'json_schema': {'name': 'realign_probe', 'schema': {
    'type': 'object', 'properties': {'value': {'type': 'number'}},
    'required': ['value'], 'additionalProperties': False}}}
TOOL = {'type': 'function', 'function': {'name': 'sum_finite',
    'description': 'Compute a sum with the local deterministic numerical tool.',
    'parameters': {'type': 'object', 'properties': {'values': {'type': 'array',
        'items': {'type': 'number'}, 'minItems': 1, 'maxItems': 8}},
        'required': ['values'], 'additionalProperties': False}}}


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON field')
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def sum_finite(arguments):
    data = strict_json(arguments)
    if type(data) is not dict or set(data) != {'values'} or type(data['values']) is not list or not 1 <= len(data['values']) <= 8:
        raise ValueError('invalid tool arguments')
    if any(type(x) not in (int, float) or not math.isfinite(x) or abs(x) > 1e4 for x in data['values']):
        raise ValueError('tool values must be bounded finite numbers')
    return math.fsum(data['values'])


def _value(text):
    obj = strict_json(text)
    if type(obj) is not dict or set(obj) != {'value'} or type(obj['value']) not in (int, float) or not math.isfinite(obj['value']):
        raise ValueError('reply failed independent closed-schema validation')
    return obj['value']


def probe_muse(client, *, source='SIMULATED_API_FIXTURE'):
    if source not in ('REAL_API', 'SIMULATED_API_FIXTURE'):
        raise ValueError('explicit probe origin required')
    calls = []
    checks = {}

    def request(operation, fn):
        try:
            result = fn()
            calls.append({'operation': operation, 'status': 'completed'})
            return result
        except Exception as exc:
            calls.append({'operation': operation, 'status': 'failed', 'error_type': type(exc).__name__,
                          'http_status': getattr(exc, 'status_code', None)})
            raise RuntimeError('API request failed; raw response/error discarded') from None

    try:
        models = request('models.list', lambda: client.models.list())
        checks['model_list'] = {'status': 'PASS' if MODEL in {m.id for m in models.data} else 'FAIL'}
    except Exception:
        checks['model_list'] = {'status': 'FAIL'}
    try:
        result = request('structured_output', lambda: client.chat.completions.create(
            model=MODEL, messages=[{'role': 'user', 'content': 'Return the number fourteen in the value field.'}],
            response_format=FORMAT, reasoning_effort='low', max_completion_tokens=2048))
        value = _value(result.choices[0].message.content)
        checks['structured_output'] = {'status': 'PASS' if value == 14 else 'FAIL', 'schema_validated': True}
    except Exception as exc:
        checks['structured_output'] = {'status': 'FAIL', 'error_type': type(exc).__name__}
    executed = 0
    try:
        messages = [{'role': 'user', 'content': 'Use sum_finite to add 17 and 29. You must obtain a local tool result. Then reply with JSON containing only value.'}]
        for turn in range(3):
            result = request('tool_round_'+str(turn+1), lambda: client.chat.completions.create(
                model=MODEL, messages=messages, tools=[TOOL], tool_choice='auto', reasoning_effort='low', max_completion_tokens=2048))
            message = result.choices[0].message
            tool_calls = message.tool_calls or []
            if tool_calls:
                if len(tool_calls) > 2 or executed+len(tool_calls) > 3:
                    raise ValueError('tool budget exceeded')
                # Preserve the assistant message INCLUDING call IDs before tool replies.
                messages.append(message.model_dump(exclude_none=True))
                for call in tool_calls:
                    if call.type != 'function' or call.function.name != 'sum_finite':
                        raise ValueError('tool name is not allowlisted')
                    value = sum_finite(call.function.arguments)
                    if value != 46:
                        raise ValueError('tool call did not compute the requested probe sum')
                    messages.append({'role': 'tool', 'tool_call_id': call.id,
                                     'content': json.dumps({'value': value}, allow_nan=False)})
                    executed += 1
            else:
                if executed == 0 or _value(message.content) != 46:
                    raise ValueError('no genuine correct local tool round trip observed')
                checks['tool_round_trip'] = {'status': 'PASS', 'executed_local_tools': executed}
                break
        else:
            raise ValueError('bounded tool round trip did not finish')
    except Exception as exc:
        checks['tool_round_trip'] = {'status': 'FAIL', 'executed_local_tools': executed, 'error_type': type(exc).__name__}
    return {'source': source, 'model': MODEL, 'status': 'PASS' if all(x['status'] == 'PASS' for x in checks.values()) else 'FAIL',
            'checks': checks, 'calls': calls,
            'successful_calls': sum(c['status'] == 'completed' for c in calls) if source == 'REAL_API' else 0,
            'failed_calls': sum(c['status'] == 'failed' for c in calls) if source == 'REAL_API' else 0,
            'documentation_mismatch': 'No live behavior assessed' if source != 'REAL_API' else 'Inspect failed capability checks; no unsupported fallback was attempted'}
