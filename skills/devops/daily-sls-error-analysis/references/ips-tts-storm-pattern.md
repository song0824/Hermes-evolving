# IPS-Specific TTS Storm Pattern (2026-08-21)

## Overview
A single IPS (Intelligent Photo Story) record's `description_tts` caused a concentrated burst of TTS conversion failures, producing 282 errors in a single hour (19:00 CST) and amplifying to 537 errors across two loggers.

## Facts (08-21)
- **Trigger**: IPS record **279555** — `description_tts` field
- **Total TTS errors**: 454 (vs 41 on 08-20, +1007%)
- **IPS 279555 contribution**: 282 errors (62% of total TTS errors)
- **Hour concentration**: 19:00 CST single hour — 574 total errors
  - `audio_generator_scheduler`: 285
  - `tts_client`: 240
- **Amplification factor**: 1 IPS record → 3 error messages × 2 loggers = 282 entries
- **Failed text sample**: `'你好呀，需要我给你一点温暖吗？,哈...'`
- **Additional IPS**: 279590 produced 6 errors (first appearance)

## Error Messages Generated
Each failed TTS conversion produces **3 parallel log entries**:
1. `ips记录 279555 description_tts生成失败: 2001001312: TTS转换异常`
2. `处理ips记录 279555 description_tts时出错: 2001001312: TTS转换异常`
3. `处理ips记录 279555 音频生成时出错: 2001001312: TTS转换异常`

Each produces entries in both `audio_generator_scheduler` (285) and `tts_client` (240) loggers.

## Root Cause Hypotheses
1. **Content issue**: IPS 279555 description_tts text contains special characters, emoji, or exceeds TTS API length limits
2. **Provider outage**: TTS supplier (感物/sensenova/火山引擎) experienced temporary API failure during 19:00-20:00 window
3. **Retry amplification**: Without retry backoff, each failed request triggers repeated attempts, multiplying errors

## Prevention Checklist
- [ ] Add length validation and truncation for `description_tts` text before TTS API call
- [ ] Add special character sanitization (emoji, surrogate pairs) before TTS
- [ ] Implement retry with exponential backoff for TTS API failures
- [ ] Add per-IPS failure circuit breaker (stop retrying after N consecutive failures for same IPS)
- [ ] Log TTS provider response codes/status for debugging

## Resolution (2026-08-22)
**Confirmed resolved**: IPS 279555 errors dropped from 282 → 0 on 08-22. Total TTS-related errors fell from 537 → 64 (audio_generator_scheduler: 291→18, tts_client: 246→46). No single IPS dominated. Remaining TTS errors scattered across multiple IPS records (281003, 280999, 280933) at 1-2 each. The storm pattern is resolved; baseline TTS errors have returned to pre-storm levels.

## Detection Pattern
When daily TTS errors exceed 3× the baseline AND a single IPS ID appears in >50% of error messages:
```
# Quick check
query: 'level: ERROR and "2001001312"' → GetHistograms
# Identify dominant IPS
query: 'level: ERROR and "2001001312" | SELECT count(1), substr(message, 1, 200) GROUP BY msg_sample'
```
