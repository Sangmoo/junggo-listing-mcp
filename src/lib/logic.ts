/**
 * 틀리면 안 되는 부분은 코드가 결정한다: 가격 범위 계산, 해시태그 정리, 결과 조립.
 * mcp_server/logic.py와 동작이 같아야 한다 (tests/fixtures/cases.json으로 양쪽을 함께 검증).
 */
export const PLATFORMS = ['당근', '번개장터', '중고나라'] as const
export type Platform = (typeof PLATFORMS)[number]
export const MAX_IMAGES = 6
const MAX_HASHTAGS = 6
const MAX_PRICE = 1_000_000_000 // 10억 초과 입력은 오타로 본다

export type Grade = 'S' | 'A' | 'B' | 'C'
export const GRADE_RATIO: Record<Grade, [number, number]> = {
  S: [0.75, 0.9],
  A: [0.6, 0.75],
  B: [0.4, 0.6],
  C: [0.2, 0.4],
}
export const GRADE_LABEL: Record<Grade, string> = {
  S: '미사용/새것 수준',
  A: '사용감 거의 없음',
  B: '생활 사용감 있음',
  C: '눈에 띄는 하자 있음',
}
export const CONFIDENCE_KO: Record<string, string> = { high: '높음', medium: '보통', low: '낮음' }

export interface PriceSuggestion {
  low: number
  high: number
  basis: string
  note: string
}

export interface Listing {
  product_name: string
  brand: string | null
  model: string | null
  category: string
  identification_confidence: 'high' | 'medium' | 'low'
  condition_grade: Grade
  condition_notes: string[]
  defects: string[]
  title: string
  description: string
  hashtags: string[]
  questions_for_seller: string[]
  privacy_warnings: string[]
  platform?: Platform
  price_suggestion?: PriceSuggestion | null
}

const won = (n: number) => n.toLocaleString('en-US')

/** 10만 원 미만은 1천 원, 이상은 5천 원 단위 사사오입. */
export function roundPrice(value: number): number {
  const unit = value < 100_000 ? 1000 : 5000
  return Math.floor(value / unit + 0.5) * unit
}

export function priceRange(purchasePrice: unknown, grade: string): PriceSuggestion | null {
  if (purchasePrice === null || purchasePrice === undefined || purchasePrice === '') return null
  const price = typeof purchasePrice === 'number' ? purchasePrice : Number(purchasePrice)
  if (!Number.isFinite(price) || price <= 0 || price > MAX_PRICE) return null
  const g: Grade = grade in GRADE_RATIO ? (grade as Grade) : 'B'
  const [lo, hi] = GRADE_RATIO[g]
  return {
    low: roundPrice(price * lo),
    high: roundPrice(price * hi),
    basis: `구매가 ${won(Math.trunc(price))}원 × 상태 ${g}등급 비율 ${Math.round(lo * 100)}~${Math.round(hi * 100)}%`,
    note: '단순 추정치입니다. 같은 모델의 최근 시세를 꼭 확인하세요.',
  }
}

export function cleanHashtags(tags: string[]): string[] {
  const out: string[] = []
  for (const raw of tags) {
    const t = raw.trim().replace(/^#+/, '').replace(/\s+/g, '')
    if (t && !out.includes(t)) out.push(t)
  }
  return out.slice(0, MAX_HASHTAGS)
}

export function finalize(data: Listing, platform: string, purchasePrice: unknown): Listing {
  return {
    ...data,
    platform: (PLATFORMS as readonly string[]).includes(platform) ? (platform as Platform) : '당근',
    hashtags: cleanHashtags(data.hashtags ?? []),
    price_suggestion: priceRange(purchasePrice, data.condition_grade ?? 'B'),
  }
}

export function renderListing(data: Listing): string {
  const lines = [data.title, '', data.description.trim()]
  const p = data.price_suggestion
  if (p) lines.push('', `희망 가격: ${won(p.low)}원 ~ ${won(p.high)}원 (조정 가능)`)
  if (data.hashtags.length) lines.push('', data.hashtags.map((t) => `#${t}`).join(' '))
  return lines.join('\n')
}
