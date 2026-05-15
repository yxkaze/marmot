"""InfoFlowChannel 测试。"""
import base64
import io
import json
from unittest.mock import MagicMock, patch

import pytest

from marmot.channels.base import ChannelError
from marmot.channels.infoflow import InfoFlowChannel


def _make_channel() -> InfoFlowChannel:
    return InfoFlowChannel(
        webhook_url="https://example.com/hi/webhook?access_token=xxx",
        to_ids=[6722554],
    )


def _make_response(body: bytes = b'{"errno": 0}', status: int = 200):
    """构造一个支持 with 语句 + .read()/.status 的伪 response。"""
    resp = MagicMock()
    resp.__enter__ = lambda self: self
    resp.__exit__ = lambda self, *a: False
    resp.status = status
    resp.read = MagicMock(return_value=body)
    return resp


def _captured_body(call) -> dict:
    """从 mocked urlopen 调用里把 POST body 解析回 dict。"""
    req = call.args[0]
    return json.loads(req.data.decode("utf-8"))


def test_constructor_validates_required_args():
    with pytest.raises(ValueError):
        InfoFlowChannel(webhook_url="", to_ids=[1])
    with pytest.raises(ValueError):
        InfoFlowChannel(webhook_url="https://x", to_ids=[])


def test_send_text_builds_envelope():
    ch = _make_channel()
    with patch("marmot.channels.infoflow.urlopen", return_value=_make_response()) as op:
        ch.send_text("hello")

    body = _captured_body(op.call_args)
    msg = body["message"]
    assert msg["header"]["toid"] == [6722554]
    assert msg["header"]["totype"] == "GROUP"
    assert msg["header"]["role"] == "robot"
    assert msg["body"][0] == {"type": "TEXT", "content": "hello"}


def test_send_text_with_at_appends_at_items():
    ch = _make_channel()
    with patch("marmot.channels.infoflow.urlopen", return_value=_make_response()) as op:
        ch.send_text("hi", at_user_ids=[1, 2])

    body_arr = _captured_body(op.call_args)["message"]["body"]
    assert body_arr[0]["type"] == "TEXT"
    assert {"type": "AT", "content": "1"} in body_arr
    assert {"type": "AT", "content": "2"} in body_arr


def test_send_link_with_at():
    ch = _make_channel()
    with patch("marmot.channels.infoflow.urlopen", return_value=_make_response()) as op:
        ch.send_link("title", "https://x", at_user_ids=[1])

    body_arr = _captured_body(op.call_args)["message"]["body"]
    assert body_arr[0]["type"] == "LINK"
    assert body_arr[0]["content"] == {"title": "title", "url": "https://x"}
    assert {"type": "AT", "content": "1"} in body_arr


def test_send_markdown_uses_md_type_and_no_at_param():
    ch = _make_channel()
    with patch("marmot.channels.infoflow.urlopen", return_value=_make_response()) as op:
        ch.send_markdown("# title")

    body_arr = _captured_body(op.call_args)["message"]["body"]
    assert body_arr == [{"type": "MD", "content": "# title"}]

    # MD 不接受 at_user_ids 参数（签名上不暴露）
    with pytest.raises(TypeError):
        ch.send_markdown("# title", at_user_ids=[1])  # type: ignore[call-arg]


def test_send_image_with_bytes_base64_encoded():
    ch = _make_channel()
    raw = b"\x89PNG\r\n\x1a\n"  # 假装是图片
    with patch("marmot.channels.infoflow.urlopen", return_value=_make_response()) as op:
        ch.send_image(raw)

    body_arr = _captured_body(op.call_args)["message"]["body"]
    assert body_arr[0]["type"] == "IMAGE"
    assert body_arr[0]["content"] == base64.b64encode(raw).decode("utf-8")


def test_send_image_with_path(tmp_path):
    ch = _make_channel()
    img = tmp_path / "x.bin"
    img.write_bytes(b"abcd")

    with patch("marmot.channels.infoflow.urlopen", return_value=_make_response()) as op:
        ch.send_image(str(img))

    body_arr = _captured_body(op.call_args)["message"]["body"]
    assert body_arr[0]["type"] == "IMAGE"
    assert body_arr[0]["content"] == base64.b64encode(b"abcd").decode("utf-8")


def test_send_image_does_not_accept_at_user_ids():
    ch = _make_channel()
    with pytest.raises(TypeError):
        ch.send_image(b"x", at_user_ids=[1])  # type: ignore[call-arg]


def test_non_2xx_raises_channel_error():
    ch = _make_channel()
    with patch(
        "marmot.channels.infoflow.urlopen",
        return_value=_make_response(status=500),
    ):
        with pytest.raises(ChannelError):
            ch.send_text("x")


def test_http_error_raises_channel_error():
    from urllib.error import HTTPError
    ch = _make_channel()
    err = HTTPError(
        "https://x", 429, "Too Many Requests", hdrs=None, fp=io.BytesIO(b"")
    )
    with patch("marmot.channels.infoflow.urlopen", side_effect=err):
        with pytest.raises(ChannelError):
            ch.send_text("x")


def test_url_error_raises_channel_error():
    from urllib.error import URLError
    ch = _make_channel()
    with patch(
        "marmot.channels.infoflow.urlopen", side_effect=URLError("dns failed")
    ):
        with pytest.raises(ChannelError):
            ch.send_text("x")


def test_invalid_json_response_raises_channel_error():
    ch = _make_channel()
    with patch(
        "marmot.channels.infoflow.urlopen",
        return_value=_make_response(body=b"not-json"),
    ):
        with pytest.raises(ChannelError):
            ch.send_text("x")


def test_returns_parsed_json():
    ch = _make_channel()
    with patch(
        "marmot.channels.infoflow.urlopen",
        return_value=_make_response(body=b'{"errno": 0, "msg": "ok"}'),
    ):
        result = ch.send_text("x")
    assert result == {"errno": 0, "msg": "ok"}
