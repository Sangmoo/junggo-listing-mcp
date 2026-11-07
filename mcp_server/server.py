"""중고거래 판매글 생성기 — 로컬 stdio MCP 서버.

실행: python mcp_server/server.py   (Claude Desktop 등 MCP 클라이언트가 실행)
Claude는 사진 분석과 글쓰기만 맡고, 가격 범위 계산과 결과 조립은 코드가 결정한다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server import MCPServer  # noqa: E402
from mcp.server.mcpserver.exceptions import ToolError as MCPToolError  # noqa: E402

from claude_util import ToolError, call_structured, file_block, resolve_client  # noqa: E402
from logic import MAX_IMAGES, PLATFORMS, finalize, render_checks, render_listing  # noqa: E402
from prompts import LISTING_SCHEMA, SYSTEM_PROMPT  # noqa: E402
from validate import normalize  # noqa: E402

server = MCPServer(
    name="junggo-listing",
    title="중고거래 판매글 생성기",
    instructions="물건 사진(로컬 파일 경로 또는 URL)으로 당근·번개장터·중고나라 판매글을 만든다.",
    version="1.0.0",
)


def run_listing(images: list[str], platform: str, seller_note: str, purchase_price: float | None) -> dict:
    if not images:
        raise ToolError("사진을 1장 이상 넣어주세요.")
    if platform not in PLATFORMS:
        platform = "당근"

    client = resolve_client()
    content = [file_block(p, allow_pdf=False) for p in images[:MAX_IMAGES]]
    content.append({
        "type": "text",
        "text": (
            f"플랫폼: {platform}\n"
            f"판매자 메모: {(seller_note or '').strip() or '없음'}\n"
            "위 사진의 물건을 판매하는 글을 작성해주세요."
        ),
    })
    raw = call_structured(
        client,
        system=SYSTEM_PROMPT,
        content=content,
        schema=LISTING_SCHEMA,
    )
    return finalize(normalize(raw, LISTING_SCHEMA), platform, purchase_price)


@server.tool()
def generate_listing(
    images: Annotated[list[str], Field(
        description="판매할 물건 사진 1~6장. 로컬 파일 절대 경로 또는 http(s) 이미지 URL. 여러 각도와 하자 부위를 함께 넣으면 정확해집니다.",
        min_length=1, max_length=MAX_IMAGES,
    )],
    platform: Annotated[Literal["당근", "번개장터", "중고나라"], Field(
        description="판매글 문체를 맞출 플랫폼.",
    )] = "당근",
    seller_note: Annotated[str, Field(
        description="판매자가 알고 있는 추가 정보 (구매 시기, 사용 기간, 구성품, 하자, 거래 방식 등). 없으면 빈 문자열.",
    )] = "",
    purchase_price: Annotated[float | None, Field(
        description="처음 샀던 가격(원). 넣으면 상태 등급 기준 희망 가격 범위를 계산해 붙입니다. 모르면 생략.",
        gt=0,
    )] = None,
) -> str:
    """중고 물건 사진으로 중고거래 판매글(제목, 본문, 해시태그)과 상태 분석 결과를 만듭니다.

    결과: 복사해서 바로 올릴 수 있는 판매글, 올리기 전 확인할 점(하자·추가 정보·개인정보 경고), 전체 분석 결과 JSON.
    가격 범위는 구매가 × 상태 등급 비율로 코드가 계산한 참고치입니다.
    """
    try:
        data = run_listing(images, platform, seller_note, purchase_price)
    except ToolError as e:
        raise MCPToolError(str(e)) from e
    return (
        "## 판매글\n\n```\n" + render_listing(data) + "\n```\n\n"
        "## 올리기 전 확인\n\n" + render_checks(data) + "\n\n"
        "## 분석 결과 JSON\n\n```json\n" + json.dumps(data, ensure_ascii=False, indent=2) + "\n```"
    )


if __name__ == "__main__":
    server.run("stdio")
