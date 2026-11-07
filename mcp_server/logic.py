"""틀리면 안 되는 부분은 코드가 결정한다: 가격 범위 계산, 해시태그 정리, 결과 조립.

src/lib/logic.ts와 동작이 같아야 한다 (tests/fixtures/cases.json으로 양쪽을 함께 검증).
"""
from __future__ import annotations

import math

PLATFORMS = ["당근", "번개장터", "중고나라"]
MAX_IMAGES = 6
MAX_HASHTAGS = 6

# 상태 등급별 구매가 대비 비율 (참고용 단순 추정)
GRADE_RATIO = {"S": (0.75, 0.90), "A": (0.60, 0.75), "B": (0.40, 0.60), "C": (0.20, 0.40)}
MAX_PRICE = 1_000_000_000  # 10억 초과 입력은 오타로 본다


def round_price(value: float) -> int:
    """10만 원 미만은 1천 원, 이상은 5천 원 단위 반올림 (사사오입, JS Math.round와 동일)."""
    unit = 1000 if value < 100_000 else 5000
    return int(math.floor(value / unit + 0.5) * unit)


def price_range(purchase_price, grade: str) -> dict | None:
    try:
        price = float(purchase_price) if purchase_price is not None else None
    except (TypeError, ValueError):
        return None
    if price is None or not math.isfinite(price) or price <= 0 or price > MAX_PRICE:
        return None
    if grade not in GRADE_RATIO:
        grade = "B"
    lo, hi = GRADE_RATIO[grade]
    return {
        "low": round_price(price * lo),
        "high": round_price(price * hi),
        "basis": f"구매가 {int(price):,}원 × 상태 {grade}등급 비율 {round(lo * 100)}~{round(hi * 100)}%",
        "note": "단순 추정치입니다. 같은 모델의 최근 시세를 꼭 확인하세요.",
    }


def clean_hashtags(tags: list[str]) -> list[str]:
    out: list[str] = []
    for t in tags:
        t = "".join(t.strip().lstrip("#").split())
        if t and t not in out:
            out.append(t)
    return out[:MAX_HASHTAGS]


def finalize(data: dict, platform: str, purchase_price) -> dict:
    """검증된 Claude 결과에 코드 계산 값을 붙인다."""
    data = dict(data)
    data["platform"] = platform if platform in PLATFORMS else "당근"
    data["hashtags"] = clean_hashtags(data.get("hashtags", []))
    data["price_suggestion"] = price_range(purchase_price, data.get("condition_grade", "B"))
    return data


def render_listing(data: dict) -> str:
    lines = [data["title"], "", data["description"].strip()]
    price = data.get("price_suggestion")
    if price:
        lines += ["", f"희망 가격: {price['low']:,}원 ~ {price['high']:,}원 (조정 가능)"]
    if data.get("hashtags"):
        lines += ["", " ".join(f"#{t}" for t in data["hashtags"])]
    return "\n".join(lines)


CONFIDENCE_KO = {"high": "높음", "medium": "보통", "low": "낮음"}


def render_checks(data: dict) -> str:
    conf = CONFIDENCE_KO.get(data["identification_confidence"], data["identification_confidence"])
    parts = [f"**식별 결과:** {data['product_name']} · 신뢰도 {conf} · 상태 {data['condition_grade']}등급"]
    if data.get("defects"):
        parts.append("**사진에서 보이는 하자**\n" + "\n".join(f"- {d}" for d in data["defects"]))
    if data.get("questions_for_seller"):
        parts.append("**글에 추가하면 좋은 정보**\n" + "\n".join(f"- {q}" for q in data["questions_for_seller"]))
    if data.get("privacy_warnings"):
        parts.append("**⚠️ 사진 속 개인정보 — 올리기 전에 가리세요**\n" + "\n".join(f"- {w}" for w in data["privacy_warnings"]))
    if data.get("price_suggestion"):
        p = data["price_suggestion"]
        parts.append(f"**가격 계산 근거:** {p['basis']}  \n{p['note']}")
    return "\n\n".join(parts)
