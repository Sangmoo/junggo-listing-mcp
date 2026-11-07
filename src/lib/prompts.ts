/** 프롬프트·스키마는 shared/prompts.json 하나를 MCP 서버와 함께 쓴다. */
import shared from '../../shared/prompts.json'
import type { JsonSchema } from './validate'

export const SYSTEM_PROMPT: string = shared.system_prompt
export const LISTING_SCHEMA = shared.schema as JsonSchema
