import json
import logging

from app.logging_config import JSONFormatter
from app.request_context import _request_id_var


def _make_record(**kwargs) -> logging.LogRecord:
    return logging.LogRecord(
        name=kwargs.get("name", "app.test"),
        level=kwargs.get("level", logging.INFO),
        pathname=__file__,
        lineno=1,
        msg=kwargs.get("msg", "hello"),
        args=None,
        exc_info=kwargs.get("exc_info"),
    )


def test_formats_basic_fields_as_valid_json():
    record = _make_record(msg="something happened")
    output = json.loads(JSONFormatter().format(record))
    assert output["message"] == "something happened"
    assert output["level"] == "INFO"
    assert output["logger"] == "app.test"
    assert "timestamp" in output


def test_includes_extra_prefixed_fields_with_prefix_stripped():
    record = _make_record()
    record.extra_status_code = 200
    record.extra_duration_ms = 12.5
    output = json.loads(JSONFormatter().format(record))
    assert output["status_code"] == 200
    assert output["duration_ms"] == 12.5


def test_ignores_non_extra_attributes():
    record = _make_record()
    record.some_other_attr = "should not appear"
    output = json.loads(JSONFormatter().format(record))
    assert "some_other_attr" not in output


def test_includes_request_id_when_set_in_context():
    token = _request_id_var.set("req-abc-123")
    try:
        output = json.loads(JSONFormatter().format(_make_record()))
        assert output["request_id"] == "req-abc-123"
    finally:
        _request_id_var.reset(token)


def test_omits_request_id_when_not_set():
    output = json.loads(JSONFormatter().format(_make_record()))
    assert "request_id" not in output


def test_includes_exception_traceback():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = _make_record(exc_info=sys.exc_info())
    output = json.loads(JSONFormatter().format(record))
    assert "boom" in output["exc_info"]
