"""Python 쪽 데이터 검증. 같은 fixture를 tests/logic.test.ts가 TypeScript 쪽에 적용한다.

실행: python -m pytest -q
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "mcp_server"))

from claude_util import ToolError  # noqa: E402
from logic import clean_hashtags, finalize, price_range, render_checks, render_listing  # noqa: E402
from prompts import LISTING_SCHEMA  # noqa: E402
from validate import normalize  # noqa: E402

CASES = json.loads((ROOT / "tests" / "fixtures" / "cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES["price_range"], ids=lambda c: f"{c['price']}-{c['grade']}")
def test_price_range(case):
    got = price_range(case["price"], case["grade"])
    exp = case["expected"]
    if exp is None:
        assert got is None
        return
    assert got["low"] == exp["low"] and got["high"] == exp["high"]
    assert got["low"] <= got["high"]
    if "basis" in exp:
        assert got["basis"] == exp["basis"]


@pytest.mark.parametrize("case", CASES["hashtags"])
def test_hashtags(case):
    assert clean_hashtags(case["input"]) == case["expected"]


@pytest.mark.parametrize("case", CASES["normalize"], ids=lambda c: c["name"])
def test_normalize(case):
    if case.get("error"):
        with pytest.raises(ToolError):
            normalize(case["input"], LISTING_SCHEMA)
    else:
        assert normalize(case["input"], LISTING_SCHEMA) == case["expected"]


def test_schema_required_keys_exist():
    props = LISTING_SCHEMA["properties"]
    assert set(LISTING_SCHEMA["required"]) <= set(props)
    for spec in props.values():
        if "enum" in spec:
            assert spec.get("default") in spec["enum"]


def test_render_end_to_end():
    data = normalize(CASES["normalize"][0]["input"], LISTING_SCHEMA)
    data = finalize(data, "번개장터", 300000)
    text = render_listing(data)
    assert text.startswith("에어팟 프로 2세대 팝니다")
    assert "희망 가격: 180,000원 ~ 225,000원" in text
    assert "#에어팟 #애플" in text
    checks = render_checks(data)
    assert "신뢰도 높음" in checks and "A등급" in checks
    assert data["platform"] == "번개장터"


def test_finalize_bad_platform_and_no_price():
    data = finalize(normalize(CASES["normalize"][0]["input"], LISTING_SCHEMA), "쿠팡", None)
    assert data["platform"] == "당근"
    assert data["price_suggestion"] is None
    assert "희망 가격" not in render_listing(data)
