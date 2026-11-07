---
title: 중고거래 판매글 생성기
emoji: 📦
colorFrom: yellow
colorTo: red
sdk: static
pinned: false
app_build_command: npm run build
app_file: dist/index.html
license: mit
short_description: 물건 사진으로 중고거래 판매글을 만드는 웹 + MCP 서버
tags:
  - korean
  - claude
  - mcp
  - vue
---

# 📦 중고거래 판매글 생성기 (웹 + MCP)

물건 사진을 넣으면 Claude가 제품과 상태를 분석해 당근·번개장터·중고나라 스타일의 판매글을 써 줍니다.

- 사진에서 보이는 하자를 숨기지 않고 정리
- 사진만으로 알 수 없는 정보는 "추가하면 좋은 정보"로 안내
- 사진 속 송장·주소·얼굴 등 개인정보 경고
- 구매가를 넣으면 상태 등급 기준 희망 가격 범위 계산 (코드 계산, 참고용)

| 사용 방법 | 위치 | 키 |
|---|---|---|
| 웹 | https://huggingface.co/spaces/Sangmoo/junggo-listing-mcp | 화면에 본인 Anthropic API 키 입력 (브라우저 → api.anthropic.com 직접 호출, 저장 서버 없음) |
| MCP 서버 | 이 저장소의 `mcp_server/` (로컬 stdio) | MCP 클라이언트 설정의 `env.ANTHROPIC_API_KEY` |

## 역할 분담

Claude는 "보고 읽고 쓰는 일"만 하고, 틀리면 안 되는 부분은 코드가 처리합니다.

| Claude | 코드 |
|---|---|
| 제품 식별, 상태 등급, 하자·개인정보 발견, 글쓰기 | 응답 스키마 검증·정규화, 희망가 범위 계산, 해시태그 정리, 결과 조립 |

Claude 응답은 `tool_choice`로 툴 호출을 강제해 항상 스키마 형태의 JSON으로 받고, 그래도 생길 수 있는 타입 어긋남(소문자 등급, 문자열로 온 배열 등)은 `validate`가 한 번 더 맞춥니다.

## 구조

```
├── shared/prompts.json      # 시스템 프롬프트 + 출력 스키마 (웹·MCP 공용, 여기만 고치면 됨)
├── src/                     # Vue 3 웹앱 (HF static Space에서 npm run build → dist/)
│   ├── App.vue
│   ├── components/          # API 키 패널, 파일 선택, 복사 버튼, MCP 안내
│   └── lib/
│       ├── claude.ts        # 브라우저에서 Messages API 호출 (tool_choice 강제)
│       ├── files.ts         # 이미지 EXIF 회전·축소(긴 변 1568px)·JPEG 변환
│       ├── validate.ts      # 스키마 기반 출력 검증·정규화
│       └── logic.ts         # 희망가 계산·결과 조립
├── mcp_server/              # 로컬 stdio MCP 서버 (Python)
│   ├── server.py            # generate_listing 툴
│   ├── claude_util.py       # 키 결정, 이미지/URL 입력, 구조화 호출
│   ├── validate.py          # validate.ts와 동일 동작
│   ├── logic.py             # logic.ts와 동일 동작
│   └── prompts.py           # shared/prompts.json 로드
└── tests/
    ├── fixtures/cases.json  # Python·TypeScript 공용 검증 데이터
    ├── test_logic.py / logic.test.ts
    └── test_server.py       # 가짜 Claude로 전체 흐름 + 실제 stdio MCP 프로토콜
```

## MCP 서버로 쓰기

```bash
git clone https://github.com/Sangmoo/junggo-listing-mcp.git
cd junggo-listing-mcp
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

`claude_desktop_config.json` (경로는 실제 위치로):

```json
{
  "mcpServers": {
    "junggo-listing": {
      "command": "C:/path/to/junggo-listing-mcp/.venv/Scripts/python.exe",
      "args": ["C:/path/to/junggo-listing-mcp/mcp_server/server.py"],
      "env": { "ANTHROPIC_API_KEY": "sk-ant-...", "CLAUDE_MODEL": "claude-sonnet-5-5" }
    }
  }
}
```

툴: `generate_listing(images, platform="당근", seller_note="", purchase_price=None)`

- `images`: 로컬 파일 절대 경로 또는 http(s) 이미지 URL, 1~6장
- `platform`: `당근` | `번개장터` | `중고나라`
- `purchase_price`: 구매가(원). 넣으면 등급별 비율(S 75~90%, A 60~75%, B 40~60%, C 20~40%)로 범위 계산

빠른 확인: `npx @modelcontextprotocol/inspector` → STDIO, command에 위 python 경로, args에 `mcp_server/server.py`.

## 개발

```bash
npm install
npm run dev          # http://localhost:5173
npm test             # TypeScript 검증 (vitest)
npm run build        # 타입 체크 + dist/ 빌드 (HF Space가 실행하는 것과 동일)

pip install -r requirements-dev.txt
python -m pytest -q  # Python 검증 + MCP stdio 프로토콜 테스트
```

## 배포

- GitHub: https://github.com/Sangmoo/junggo-listing-mcp
- Hugging Face Space(static): https://huggingface.co/spaces/Sangmoo/junggo-listing-mcp — `main`에 push하면 Space가 `npm run build` 후 `dist/index.html`을 서빙

결과는 참고용입니다. 가격은 구매가와 상태 등급으로 계산한 단순 추정치이며, 제품 식별과 정품 여부는 직접 확인하세요.
