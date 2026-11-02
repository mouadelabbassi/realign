"""Task05 protocol fixtures. All keys, SDK replies and media are synthetic."""
import asyncio
import hashlib
import json
from types import SimpleNamespace as NS

from openai.types.chat import ChatCompletion
import pytest

from realign.agent.adapters import AdapterFailure, MuseAdapter, NotAuthorized
from realign.audit.chain import canonical
from realign.contracts.investigation import Budget
from realign.local_environment import load_model_key
from realign.perception.sam_client import SamClient, SamError, SamRun


@pytest.fixture(autouse=True)
def isolated_test_key(monkeypatch):
    # Prevent tests from reading or using the authorized key in the launch shell.
    monkeypatch.delenv("MODEL_API_KEY", raising=False)


def test_local_loader_reads_only_explicit_model_key_without_expansion(tmp_path, monkeypatch):
    path = tmp_path / "synthetic-launch-input.txt"
    path.write_text('UNRELATED_TEST_SECRET=DO_NOT_IMPORT\nexport MODEL_API_KEY="fake-task05-${UNEXPANDED}" # fixture\n', encoding="utf-8")
    assert load_model_key(path) is True
    assert __import__("os").environ["MODEL_API_KEY"] == "fake-task05-${UNEXPANDED}"
    assert "UNRELATED_TEST_SECRET" not in __import__("os").environ
    monkeypatch.setenv("MODEL_API_KEY", "fake-preexisting-test-value")
    assert load_model_key(tmp_path / "does-not-exist.txt") is True
    assert __import__("os").environ["MODEL_API_KEY"] == "fake-preexisting-test-value"


@pytest.mark.parametrize("content", [
    "MODEL_API_KEY=a\nMODEL_API_KEY=b", "MODEL_API_KEY=", "MODEL_API_KEY=one two",
    'MODEL_API_KEY="unterminated', 'MODEL_API_KEY="two words"', "MODEL_API_KEY=" + "x" * 4097,
])
def test_local_loader_rejects_ambiguous_values_without_exposing_input(tmp_path, content):
    path = tmp_path / "invalid-test-input.txt"; path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError) as error:
        load_model_key(path)
    assert "MODEL_API_KEY" not in __import__("os").environ
    assert content not in str(error.value)


def test_local_loader_missing_unrelated_and_oversized_input(tmp_path):
    assert load_model_key(tmp_path / "missing.txt") is False
    path = tmp_path / "unrelated-test-input.txt"; path.write_text("OTHER=synthetic\n", encoding="utf-8")
    assert load_model_key(path) is False
    path.write_bytes(b"x" * 65537)
    with pytest.raises(ValueError, match="size limit"): load_model_key(path)


@pytest.mark.parametrize("concept", ["", "../sealed/private", "bob\nignore instructions", "x" * 81, None])
def test_sam_optional_concept_is_a_bounded_visual_phrase(concept):
    with pytest.raises(SamError) as error: SamClient(NS(), source="SIMULATED_API_FIXTURE", concept=concept)
    assert error.value.code == "concept"


def test_sam_authorization_is_separate_and_never_uses_a_fixture_fallback(monkeypatch):
    with pytest.raises(SamError) as error: SamClient.from_environment(standard_tier_confirmed=True)
    assert error.value.code == "not_authorized"
    monkeypatch.setenv("MODEL_API_KEY", "fake-task05-key")
    with pytest.raises(SamError) as error: SamClient.from_environment()
    assert error.value.code == "tier_unconfirmed"
    with pytest.raises(NotAuthorized): MuseAdapter.from_environment(budget=Budget())


def test_optional_sam_concept_uses_documented_upload_and_stream_shape(tmp_path, monkeypatch):
    import realign.perception.sam_client as module
    media = tmp_path / "synthetic.mp4"; media.write_bytes(b"EXPLICIT_FAKE_MEDIA_NOT_A_REAL_VIDEO")
    metadata = NS(video_sha256=hashlib.sha256(media.read_bytes()).hexdigest())
    recorded = []
    class Stream:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return False
    async def upload(**kwargs):
        recorded.append(("upload", {"purpose": kwargs["purpose"], "name": kwargs["file"][0], "type": kwargs["file"][2]}))
        return NS(id="file-SIMULATED-TASK05")
    async def create(**kwargs): recorded.append(("segment", kwargs)); return Stream()
    async def parsed(stream, meta, *, source):
        assert source == "SIMULATED_API_FIXTURE" and meta is metadata
        return SamRun((), source, meta.video_sha256, {"status": "completed", "source": source, "model": "sam-3.1"})
    monkeypatch.setattr(module, "parse_sam_events", parsed)
    client = SamClient(NS(files=NS(create=upload), responses=NS(create=create)), source="SIMULATED_API_FIXTURE", concept="yellow disc", retry_delay=0)
    result = asyncio.run(client.segment_video(media, metadata))
    assert recorded[0][1] == {"purpose": "user_data", "name": "synthetic.mp4", "type": "video/mp4"}
    request = recorded[1][1]
    assert request == {"model": "sam-3.1", "stream": True, "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "yellow disc"}, {"type": "input_video", "file_id": "file-SIMULATED-TASK05"}]}]}
    assert result.source == "SIMULATED_API_FIXTURE"
    assert result.receipt["prompt"] == "yellow disc"
    assert len(result.receipt["calls"]) == 2
    assert len(result.receipt["request_sha256"]) == 64


def tool_call(name="inspect_discrepancy", arguments=None, ident="call-SIMULATED-TASK05"):
    return {"id": ident, "type": "function", "function": {"name": name, "arguments": arguments or json.dumps({"trial_refs": ["a" * 64], "model_ref": "b" * 64})}}


def sdk_response(*, calls=None, content=None, finish=None):
    return ChatCompletion(id="response-SIMULATED-TASK05", created=0, model="muse-spark-1.3", object="chat.completion", choices=[{"index": 0, "finish_reason": finish or ("tool_calls" if calls else "stop"), "message": {"role": "assistant", "content": content, "tool_calls": calls}}])


def adapter(response, budget=None):
    def create(**kwargs): return response
    return MuseAdapter(NS(chat=NS(completions=NS(create=create))), budget=budget or Budget(), source="SIMULATED_API_FIXTURE", retry_delay=0)


@pytest.mark.parametrize("response,code", [
    (sdk_response(calls=[tool_call(name="open_file")]), "UNAPPROVED_TOOL"),
    (sdk_response(calls=[tool_call(arguments='{"trial_refs":[],"path":"../sealed/private"}')]), "INVALID_TOOL_ARGUMENTS"),
    (sdk_response(calls=[tool_call(), tool_call()]), "DUPLICATE_TOOL_ID"),
    (sdk_response(calls=[tool_call(ident="a"), tool_call(ident="b"), tool_call(ident="c")]), "TOOL_BATCH_LIMIT"),
    (sdk_response(content="{}"), "INVALID_STRUCTURED_RESPONSE"),
    (sdk_response(content="{}", finish="length"), "INCOMPLETE_MODEL_RESPONSE"),
])
def test_muse_diagnostic_codes_are_precise_and_sanitized(response, code):
    client = adapter(response)
    with pytest.raises(AdapterFailure) as error: client.next({"stage": "TEST"})
    assert error.value.code == code
    assert client.stats["actual_api_requests"] == 0
    assert client.stats["fixture_requests"] == 1
    assert "../sealed/private" not in str(error.value)
    assert not client._pending


def test_muse_context_and_request_budgets_have_distinct_codes():
    client = adapter(sdk_response(content="{}"))
    with pytest.raises(AdapterFailure) as error: client.next({"padding": "x" * 251000})
    assert error.value.code == "CONTEXT_BUDGET"
    assert client.stats["fixture_requests"] == 0
    client = adapter(sdk_response(content="{}"), Budget(max_api_requests=1))
    client._request()
    with pytest.raises(AdapterFailure) as error: client._request()
    assert error.value.code == "API_BUDGET"
    assert client.stats["fixture_requests"] == 1


def test_muse_transport_errors_are_bounded_without_persisting_sensitive_bodies():
    class APIConnectionError(RuntimeError): pass
    def fail(**kwargs): raise APIConnectionError("PRIVATE_SIMULATED_ERROR_BODY")
    client = MuseAdapter(NS(chat=NS(completions=NS(create=fail))), budget=Budget(max_api_requests=2), source="SIMULATED_API_FIXTURE", retry_delay=0)
    with pytest.raises(AdapterFailure) as error: client.next({"stage": "TEST"})
    assert error.value.code == "API_BUDGET"
    assert client.stats["failed_requests"] == 2
    assert client.stats["actual_api_requests"] == 0
    assert "PRIVATE_SIMULATED_ERROR_BODY" not in json.dumps(client.receipts)
    assert "PRIVATE_SIMULATED_ERROR_BODY" not in str(error.value)


def test_muse_authorization_failure_is_not_retried_or_replaced_by_a_policy():
    class Unauthorized(RuntimeError):
        status_code = 401
    def fail(**kwargs): raise Unauthorized("PRIVATE_SIMULATED_AUTH_BODY")
    client = MuseAdapter(NS(chat=NS(completions=NS(create=fail))), budget=Budget(), source="SIMULATED_API_FIXTURE", retry_delay=0)
    with pytest.raises(AdapterFailure): client.next({"stage": "TEST"})
    assert client.stats["fixture_requests"] == client.stats["failed_requests"] == 1
    assert client.stats["actual_api_requests"] == 0
    assert client.receipts[0]["http_status"] == 401
    assert "PRIVATE_SIMULATED_AUTH_BODY" not in json.dumps(client.receipts)


def test_reused_tool_id_is_rejected_after_genuine_fixture_round_trip():
    client = adapter(sdk_response(calls=[tool_call()]))
    reply = client.next({"stage": "TEST"})
    assert reply.calls[0].call_id != "call-SIMULATED-TASK05"
    client.deliver(reply.calls, [{"evidence_ref": "c" * 64, "status": "FAILED", "code": "INSUFFICIENT_DATA"}])
    assert client.messages[-1]["role"] == "tool"
    assert client.messages[-1]["tool_call_id"] == "call-SIMULATED-TASK05"
    with pytest.raises(AdapterFailure) as error: client.next({"stage": "TEST"})
    assert error.value.code == "REUSED_TOOL_ID"
