<script setup lang="ts">
/**
 * 중고거래 판매글 생성기.
 * Claude는 사진 분석과 글쓰기만 맡고, 가격 범위 계산·결과 조립은 코드(lib/logic.ts)가 한다.
 */
import { computed, ref } from 'vue'
import ApiKeyPanel from '@/components/ApiKeyPanel.vue'
import CopyButton from '@/components/CopyButton.vue'
import FilePicker from '@/components/FilePicker.vue'
import McpGuide from '@/components/McpGuide.vue'
import { DEFAULT_MODEL, callStructured, type ContentBlock } from '@/lib/claude'
import { ToolError } from '@/lib/errors'
import { fileToBlock } from '@/lib/files'
import {
  CONFIDENCE_KO,
  GRADE_LABEL,
  MAX_IMAGES,
  PLATFORMS,
  finalize,
  renderListing,
  type Listing,
  type Platform,
} from '@/lib/logic'
import { LISTING_SCHEMA, SYSTEM_PROMPT } from '@/lib/prompts'
import { loadModel } from '@/lib/storage'
import { normalize } from '@/lib/validate'

const apiKey = ref('')
const model = ref(loadModel(DEFAULT_MODEL))
const images = ref<File[]>([])
const platform = ref<Platform>('당근')
const sellerNote = ref('')
const priceText = ref('')

const loading = ref(false)
const error = ref('')
const result = ref<Listing | null>(null)
const listingText = ref('')
let controller: AbortController | null = null

const purchasePrice = computed(() => {
  const digits = priceText.value.replace(/[^\d]/g, '')
  return digits ? Number(digits) : null
})
function formatPrice() {
  if (purchasePrice.value) priceText.value = purchasePrice.value.toLocaleString('en-US')
}

const canSubmit = computed(() => !loading.value && images.value.length > 0 && apiKey.value.trim() !== '')

async function submit() {
  error.value = ''
  if (!apiKey.value.trim()) return void (error.value = '먼저 Anthropic API 키를 입력해주세요.')
  if (!images.value.length) return void (error.value = '사진을 1장 이상 넣어주세요.')

  loading.value = true
  controller = new AbortController()
  try {
    const content: ContentBlock[] = []
    for (const f of images.value.slice(0, MAX_IMAGES)) content.push(await fileToBlock(f, false))
    content.push({
      type: 'text',
      text: `플랫폼: ${platform.value}\n판매자 메모: ${sellerNote.value.trim() || '없음'}\n위 사진의 물건을 판매하는 글을 작성해주세요.`,
    })
    const raw = await callStructured({
      apiKey: apiKey.value,
      model: model.value,
      system: SYSTEM_PROMPT,
      content,
      schema: LISTING_SCHEMA,
      signal: controller.signal,
    })
    const data = finalize(normalize<Listing>(raw, LISTING_SCHEMA), platform.value, purchasePrice.value)
    result.value = data
    listingText.value = renderListing(data)
    requestAnimationFrame(() => document.getElementById('result')?.scrollIntoView({ behavior: 'smooth' }))
  } catch (e) {
    error.value = e instanceof ToolError ? e.message : `알 수 없는 오류: ${(e as Error).message}`
  } finally {
    loading.value = false
    controller = null
  }
}

function cancel() {
  controller?.abort()
}

const jsonText = computed(() => (result.value ? JSON.stringify(result.value, null, 2) : ''))
</script>

<template>
  <main class="wrap">
    <header class="top">
      <h1>📦 중고거래 판매글 생성기</h1>
      <p>물건 사진을 올리면 당근·번개장터·중고나라 스타일 판매글을 써 드립니다. 하자와 사진 속 개인정보도 함께 짚어 드려요.</p>
    </header>

    <ApiKeyPanel v-model:api-key="apiKey" v-model:model="model" />

    <form class="card" @submit.prevent="submit">
      <FilePicker
        v-model="images"
        :max="MAX_IMAGES"
        accept="image/*"
        label="물건 사진"
        hint="여러 각도 + 하자 부위를 함께 넣으면 정확해집니다"
      />

      <fieldset class="seg">
        <legend class="legend">플랫폼 문체</legend>
        <label v-for="p in PLATFORMS" :key="p">
          <input type="radio" name="platform" :value="p" v-model="platform" />
          <span>{{ p }}</span>
        </label>
      </fieldset>

      <label class="field">
        <span>추가 정보 (선택)</span>
        <textarea v-model="sellerNote" rows="3" placeholder="예: 작년 3월 구매, 박스·충전기 있음, 직거래 선호"></textarea>
      </label>

      <label class="field">
        <span>구매가 (원, 선택)</span>
        <input
          type="text"
          inputmode="numeric"
          v-model="priceText"
          @blur="formatPrice"
          placeholder="예: 350,000 — 넣으면 상태 등급 기준 희망 가격 범위를 계산합니다"
        />
      </label>

      <div v-if="error" class="error" role="alert">{{ error }}</div>

      <div class="actions">
        <button class="primary" type="submit" :disabled="!canSubmit">
          <template v-if="loading"><span class="spinner"></span>사진 분석하고 글 쓰는 중…</template>
          <template v-else>판매글 만들기</template>
        </button>
        <button v-if="loading" type="button" class="ghost" @click="cancel">취소</button>
      </div>
      <p class="hint">사진은 이 브라우저에서 줄인 뒤 Claude API로만 전송되며 저장되지 않습니다.</p>
    </form>

    <section v-if="result" id="result">
      <div class="card">
        <div class="result-head">
          <h2>판매글</h2>
          <CopyButton :text="listingText" label="전체 복사" />
        </div>
        <textarea v-model="listingText" rows="14" aria-label="판매글 (수정 가능)"></textarea>
        <p class="hint">그대로 복사해 쓰거나 여기서 고친 뒤 복사하세요.</p>
      </div>

      <div class="card">
        <h2>올리기 전 확인</h2>
        <div v-if="result.privacy_warnings.length" class="alert">
          <h3>⚠️ 사진 속 개인정보 — 올리기 전에 가리세요</h3>
          <ul>
            <li v-for="w in result.privacy_warnings" :key="w">{{ w }}</li>
          </ul>
        </div>
        <div class="chips">
          <span class="chip accent">{{ result.product_name }}</span>
          <span class="chip">식별 신뢰도 {{ CONFIDENCE_KO[result.identification_confidence] }}</span>
          <span class="chip">상태 {{ result.condition_grade }}등급 · {{ GRADE_LABEL[result.condition_grade] }}</span>
          <span class="chip">{{ result.category }}</span>
        </div>
        <template v-if="result.defects.length">
          <h3>사진에서 보이는 하자</h3>
          <ul class="plain">
            <li v-for="d in result.defects" :key="d">{{ d }}</li>
          </ul>
        </template>
        <template v-if="result.questions_for_seller.length">
          <h3>글에 추가하면 좋은 정보</h3>
          <ul class="plain">
            <li v-for="q in result.questions_for_seller" :key="q">{{ q }}</li>
          </ul>
        </template>
        <template v-if="result.price_suggestion">
          <h3>희망 가격 {{ result.price_suggestion.low.toLocaleString('en-US') }}원 ~ {{ result.price_suggestion.high.toLocaleString('en-US') }}원</h3>
          <p class="muted">{{ result.price_suggestion.basis }}<br />{{ result.price_suggestion.note }}</p>
        </template>
        <p v-else class="hint">구매가를 넣으면 상태 등급 기준 희망 가격 범위를 계산해 드립니다.</p>
      </div>

      <details class="card">
        <summary><span>분석 결과 JSON</span></summary>
        <pre><code>{{ jsonText }}</code></pre>
      </details>
    </section>

    <McpGuide server-name="junggo-listing" repo="junggo-listing-mcp" tool="generate_listing" />

    <footer class="foot">
      가격은 구매가와 상태 등급으로 계산한 단순 참고치입니다. 제품 식별과 정품 여부는 직접 확인하세요.
    </footer>
  </main>
</template>
