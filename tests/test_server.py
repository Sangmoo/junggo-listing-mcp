"""MCP 서버 검증.

1) 가짜 Anthropic 클라이언트로 입력 변환 → Claude 호출 → 검증 → 결과 조립 전체 흐름
2) 실제 stdio 프로세스를 띄워 MCP 프로토콜(initialize / list_tools / call_tool 오류 경로) 확인
"""
import asyncio
import io
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "mcp_server"))

import claude_util  # noqa: E402
import server  # noqa: E402
from claude_util import ToolError  # noqa: E402

FAKE_OUTPUT = {
    "product_name": "원목 의자 (추정)", "brand": "", "category": "가구",
    "identification_confidence": "medium", "condition_grade": "b",
    "condition_notes": "다리 흔들림 없음", "defects": ["좌판 모서리 찍힘"],
    "title": "원목 의자 팝니다", "description": "튼튼한 원목 의자예요.",
    "hashtags": ["#원목의자", "의자", "원목 의자"], "questions_for_seller": ["구매 시기"],
    "privacy_warnings": [],
}


class FakeMessages:
    def __init__(self, output, stop_reason="end_turn"):
        self.output, self.stop_reason, self.calls = output, stop_reason, []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            stop_reason=self.stop_reason,
            content=[SimpleNamespace(type="text", text=json.dumps(self.output, ensure_ascii=False))],
        )


@pytest.fixture
def photo(tmp_path):
    p = tmp_path / "chair.png"
    Image.new("RGBA", (3000, 2000), (160, 82, 45, 255)).save(p)
    return str(p)


@pytest.fixture
def fake(monkeypatch):
    messages = FakeMessages(FAKE_OUTPUT)
    monkeypatch.setattr(server, "resolve_client", lambda: SimpleNamespace(messages=messages))
    return messages


def test_full_flow(photo, fake):
    data = server.run_listing([photo], "번개장터", "작년 구매", 120000)
    call = fake.calls[0]
    assert "tool_choice" not in call and "tools" not in call  # Sonnet/Opus 5.5는 강제 tool_choice 거부
    schema = call["output_config"]["format"]["schema"]
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert schema["additionalProperties"] is False
    assert "default" not in json.dumps(schema)  # structured outputs 미지원 키워드 제거
    blocks = call["messages"][0]["content"]
    assert [b["type"] for b in blocks] == ["image", "text"]
    img = Image.open(io.BytesIO(__import__("base64").b64decode(blocks[0]["source"]["data"])))
    assert max(img.size) == claude_util.MAX_SIDE and img.format == "JPEG"
    assert "번개장터" in blocks[1]["text"] and "작년 구매" in blocks[1]["text"]

    assert data["condition_grade"] == "B"
    assert data["brand"] is None
    assert data["hashtags"] == ["원목의자", "의자"]
    assert data["price_suggestion"]["low"] == 48000 and data["price_suggestion"]["high"] == 72000


def test_tool_output_text(photo, fake):
    out = server.generate_listing([photo], "당근", "", None)
    assert "## 판매글" in out and "원목 의자 팝니다" in out and "희망 가격" not in out


def test_images_capped(photo, fake):
    server.run_listing([photo] * 9, "당근", "", None)
    blocks = fake.calls[0]["messages"][0]["content"]
    assert sum(b["type"] == "image" for b in blocks) == 6


def test_errors(photo, tmp_path, monkeypatch):
    with pytest.raises(ToolError, match="1장 이상"):
        server.run_listing([], "당근", "", None)
    with pytest.raises(ToolError, match="찾을 수 없습니다"):
        claude_util.file_block(str(tmp_path / "nope.jpg"))
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"not an image")
    with pytest.raises(ToolError, match="읽을 수 없습니다"):
        claude_util.file_block(str(bad))
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")
    with pytest.raises(ToolError, match="PDF"):
        claude_util.file_block(str(pdf), allow_pdf=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ToolError, match="API 키가 없습니다"):
        claude_util.resolve_client()


def test_truncated_response(photo, monkeypatch):
    messages = FakeMessages(FAKE_OUTPUT, stop_reason="max_tokens")
    monkeypatch.setattr(server, "resolve_client", lambda: SimpleNamespace(messages=messages))
    with pytest.raises(ToolError, match="잘렸습니다"):
        server.run_listing([photo], "당근", "", None)


def test_stdio_protocol(photo):
    """실제 MCP 클라이언트로 stdio 서버를 띄워 확인 (키 없음 → 친절한 오류)."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "mcp_server" / "server.py")], env=env)

    async def run():
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                tools = (await s.list_tools()).tools
                res = await s.call_tool("generate_listing", {"images": [photo], "platform": "당근"})
                return tools, res

    tools, res = asyncio.run(run())
    assert [t.name for t in tools] == ["generate_listing"]
    assert tools[0].input_schema["properties"]["platform"]["enum"] == ["당근", "번개장터", "중고나라"]
    assert res.is_error
    assert "API 키가 없습니다" in res.content[0].text
