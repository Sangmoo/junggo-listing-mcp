"""Claude 호출 공통 유틸 (로컬 stdio MCP 서버용, 두 프로젝트 공통).

- API 키: 환경변수 ANTHROPIC_API_KEY (MCP 클라이언트 설정의 env로 전달)
- 이미지/PDF(로컬 경로 또는 http(s) URL)를 Claude 입력 블록으로 변환
- structured outputs(output_config.format)로 항상 스키마에 맞는 JSON을 받음
  (Sonnet 5.5 / Opus 5.5는 tool_choice로 툴 호출을 강제하는 방식을 400으로 거부한다)
"""
from __future__ import annotations

import base64
import datetime
import io
import json
import os
import urllib.request
from pathlib import Path

import anthropic
from PIL import Image, ImageOps, UnidentifiedImageError

MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
MAX_SIDE = 1568  # 이 이상은 Claude가 내부적으로 축소하므로 미리 줄여 전송량/비용 절감
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_PDF_BYTES = 32 * 1024 * 1024  # Claude PDF 입력 한도

KST = datetime.timezone(datetime.timedelta(hours=9))


class ToolError(Exception):
    """사용자에게 그대로 보여줄 수 있는 오류."""


def today_kst() -> datetime.date:
    return datetime.datetime.now(KST).date()


def resolve_client(api_key: str | None = None) -> anthropic.Anthropic:
    key = (api_key or os.getenv("ANTHROPIC_API_KEY") or "").strip()
    if not key:
        raise ToolError(
            "API 키가 없습니다. MCP 클라이언트 설정의 env에 ANTHROPIC_API_KEY를 넣어주세요."
        )
    return anthropic.Anthropic(api_key=key)


# ---------- 입력 파일 ----------

def _read_source(src: str) -> tuple[bytes, str]:
    """로컬 경로 또는 URL에서 바이트와 이름(확장자 판별용)을 읽는다."""
    src = src.strip()
    if src.startswith(("http://", "https://")):
        req = urllib.request.Request(src, headers={"User-Agent": "mcp-file-fetch/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data = r.read(MAX_PDF_BYTES + 1)
                ctype = r.headers.get("Content-Type", "")
        except Exception as e:  # noqa: BLE001 - 네트워크 오류를 사용자 메시지로 변환
            raise ToolError(f"URL에서 파일을 받지 못했습니다: {src} ({e})") from e
        name = src.split("?")[0]
        if "pdf" in ctype and not name.lower().endswith(".pdf"):
            name += ".pdf"
    else:
        path = Path(src).expanduser()
        if not path.is_file():
            raise ToolError(f"파일을 찾을 수 없습니다: {src}")
        if path.stat().st_size > MAX_PDF_BYTES:
            raise ToolError(f"파일이 너무 큽니다(32MB 초과): {src}")
        data, name = path.read_bytes(), path.name
    if not data:
        raise ToolError(f"빈 파일입니다: {src}")
    return data, name


def _is_pdf(data: bytes, name: str) -> bool:
    return data[:5] == b"%PDF-" or name.lower().endswith(".pdf")


def image_block_from_bytes(data: bytes, label: str = "이미지") -> dict:
    """이미지 → JPEG base64 블록 (EXIF 회전 보정, 긴 변 MAX_SIDE로 축소)."""
    if len(data) > MAX_FILE_BYTES:
        raise ToolError(f"{label}가 너무 큽니다(20MB 초과).")
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img).convert("RGB")
    except (UnidentifiedImageError, OSError) as e:
        raise ToolError(f"{label}를 읽을 수 없습니다. JPG·PNG·WEBP로 변환해 주세요.") from e
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/jpeg",
            "data": base64.standard_b64encode(buf.getvalue()).decode(),
        },
    }


def pdf_block_from_bytes(data: bytes) -> dict:
    return {
        "type": "document",
        "source": {
            "type": "base64",
            "media_type": "application/pdf",
            "data": base64.standard_b64encode(data).decode(),
        },
    }


def file_block(src: str, allow_pdf: bool = True) -> dict:
    data, name = _read_source(src)
    if _is_pdf(data, name):
        if not allow_pdf:
            raise ToolError(f"PDF는 지원하지 않습니다. 사진 파일을 넣어주세요: {src}")
        return pdf_block_from_bytes(data)
    return image_block_from_bytes(data, label=Path(name).name or "이미지")


# ---------- Claude 호출 ----------

def call_structured(
    client: anthropic.Anthropic,
    system: str,
    content: list[dict],
    schema: dict,
    max_tokens: int = 16000,
) -> dict:
    """structured outputs로 스키마에 맞는 JSON을 받아 dict로 돌려준다."""
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": content}],
            output_config={"format": {"type": "json_schema", "schema": to_api_schema(schema)}},
        )
    except anthropic.AuthenticationError as e:
        raise ToolError("Anthropic API 키가 올바르지 않습니다.") from e
    except anthropic.RateLimitError as e:
        raise ToolError("Anthropic API 요청 한도에 걸렸습니다. 잠시 후 다시 시도해주세요.") from e
    except anthropic.BadRequestError as e:
        raise ToolError(f"요청이 거부되었습니다: {e.message}") from e
    except anthropic.APIError as e:
        raise ToolError(f"Claude API 호출 중 오류가 발생했습니다: {e}") from e

    if resp.stop_reason == "refusal":
        raise ToolError("Claude가 이 요청의 처리를 거절했습니다. 다른 사진으로 시도해주세요.")
    if resp.stop_reason == "max_tokens":
        raise ToolError("응답이 길어 중간에 잘렸습니다. 파일 수를 줄여 다시 시도해주세요.")
    text = next((b.text for b in resp.content if b.type == "text"), None)
    if not text:
        raise ToolError("Claude 응답에서 결과를 찾지 못했습니다. 다시 시도해주세요.")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ToolError("Claude 응답을 해석하지 못했습니다. 다시 시도해주세요.") from e


# structured outputs가 받지 않는 키워드
_UNSUPPORTED = {"default", "minimum", "maximum", "multipleOf", "minLength", "maxLength", "minItems", "maxItems"}


def to_api_schema(schema):
    """output_config.format용 스키마: 모든 object에 additionalProperties: false, 미지원 키워드 제거.
    (src/lib/claude.ts의 toApiSchema와 동일)"""
    if isinstance(schema, list):
        return [to_api_schema(s) for s in schema]
    if not isinstance(schema, dict):
        return schema
    out = {k: to_api_schema(v) for k, v in schema.items() if k not in _UNSUPPORTED}
    if schema.get("properties") is not None:
        out["properties"] = {k: to_api_schema(v) for k, v in schema["properties"].items()}
    t = out.get("type")
    if t == "object" or (isinstance(t, list) and "object" in t):
        out["additionalProperties"] = False
    return out
