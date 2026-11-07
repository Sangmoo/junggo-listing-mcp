/** TypeScript 쪽 데이터 검증. tests/test_logic.py와 같은 fixture를 쓴다. 실행: npm test */
import { describe, expect, it } from 'vitest'
import cases from './fixtures/cases.json'
import { ToolError } from '../src/lib/errors'
import { cleanHashtags, finalize, priceRange, renderListing, type Listing } from '../src/lib/logic'
import { LISTING_SCHEMA } from '../src/lib/prompts'
import { normalize } from '../src/lib/validate'

describe('priceRange', () => {
  for (const c of cases.price_range) {
    it(`${c.price} / ${c.grade}`, () => {
      const got = priceRange(c.price, c.grade)
      const exp = c.expected as { low: number; high: number; basis?: string } | null
      if (exp === null) {
        expect(got).toBeNull()
        return
      }
      expect(got).not.toBeNull()
      expect(got!.low).toBe(exp.low)
      expect(got!.high).toBe(exp.high)
      expect(got!.low).toBeLessThanOrEqual(got!.high)
      if (exp.basis) expect(got!.basis).toBe(exp.basis)
    })
  }
})

describe('cleanHashtags', () => {
  for (const c of cases.hashtags) {
    it(JSON.stringify(c.input), () => expect(cleanHashtags(c.input)).toEqual(c.expected))
  }
})

describe('normalize', () => {
  for (const c of cases.normalize) {
    it(c.name, () => {
      if ('error' in c && c.error) {
        expect(() => normalize(c.input, LISTING_SCHEMA)).toThrow(ToolError)
      } else {
        expect(normalize(c.input, LISTING_SCHEMA)).toEqual((c as { expected: unknown }).expected)
      }
    })
  }
})

describe('render', () => {
  it('판매글 조립', () => {
    const data = finalize(normalize<Listing>(cases.normalize[0].input, LISTING_SCHEMA), '번개장터', 300000)
    const text = renderListing(data)
    expect(text.startsWith('에어팟 프로 2세대 팝니다')).toBe(true)
    expect(text).toContain('희망 가격: 180,000원 ~ 225,000원')
    expect(text).toContain('#에어팟 #애플')
    expect(data.platform).toBe('번개장터')
  })
  it('잘못된 플랫폼·구매가 없음', () => {
    const data = finalize(normalize<Listing>(cases.normalize[0].input, LISTING_SCHEMA), '쿠팡', null)
    expect(data.platform).toBe('당근')
    expect(data.price_suggestion).toBeNull()
    expect(renderListing(data)).not.toContain('희망 가격')
  })
})

describe('toApiSchema', () => {
  it('모든 object에 additionalProperties: false, default 제거', async () => {
    const { toApiSchema } = await import('../src/lib/claude')
    const s = toApiSchema(LISTING_SCHEMA) as Record<string, any>
    expect(s.additionalProperties).toBe(false)
    expect(JSON.stringify(s)).not.toContain('"default"')
    expect(s.properties.condition_grade.enum).toEqual(['S', 'A', 'B', 'C'])
    expect(Object.keys(s.properties)).toEqual(Object.keys(LISTING_SCHEMA.properties!))
  })
})
