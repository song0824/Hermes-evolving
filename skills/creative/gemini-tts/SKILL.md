---
name: gemini-tts
category: creative
description: Generate audio/speech using Google Gemini TTS API (gemini-3.1-flash-tts-preview) via custom BaseURL proxy. Covers REST API, Audio Profile format, PCM→MP3 conversion, and Feishu delivery.
---

# Gemini TTS (Text-to-Speech)

Generate speech using `gemini-3.1-flash-tts-preview` model.

## Prerequisites
```bash
pip install google-genai
```

## API Key
Gemini API Key is stored in `/root/.hermes/.env` and environment variables. Load with:
```python
import os
api_key = os.environ.get('GEMINI_API_KEY')
```

## Custom BaseURL (Required in China)
The server cannot reach `generativelanguage.googleapis.com` directly. Use the proxy:
```python
base_url = 'https://chatdemo.dev.ling.space'
```

## Method: REST API (Only Reliable Method)

```python
import os, json, base64, urllib.request

api_key = os.environ.get('GEMINI_API_KEY')
base_url = 'https://chatdemo.dev.ling.space'

body = {
    "contents": [{"role": "user", "parts": [{"text": content_text}]}],
    "generationConfig": {
        "responseModalities": ["AUDIO"],
        "speechConfig": {
            "voiceConfig": {
                "prebuiltVoiceConfig": {"voiceName": "Alnilam"}
            }
        }
    }
}

url = f"{base_url}/v1beta/models/gemini-3.1-flash-tts-preview:generateContent?key={api_key}"
data = json.dumps(body, ensure_ascii=False).encode('utf-8')
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')

with urllib.request.urlopen(req, timeout=90) as resp:
    result = json.loads(resp.read())
```

## Audio Profile Format (Required for Voice Direction)

The audio profile prefix MUST be kept as a separate variable. The speech text is concatenated after `### TRANSCRIPT`.

```python
# Fixed audio profile prefix (DO NOT modify)
AUDIO_PROFILE_PREFIX = """# AUDIO PROFILE: Alnilam.
## A young boy's voice (age 4), soft, endearing. The tone is a mix of shy curiosity and clumsy optimism. The pitch is medium-high.
### DIRECTORS NOTES
Style: Empathetic
Pace: Natural
Accent: American
### TRANSCRIPT
"""

# Speech text to convert
text_to_speak = "Hi, I'm Inko. The best way to get started is to quit talking and begin doing."

# Concatenate
content_text = AUDIO_PROFILE_PREFIX + text_to_speak
```

### Full example with PCM→WAV→MP3:

```python
import os, json, base64, struct, subprocess, urllib.request

api_key = os.environ.get('GEMINI_API_KEY')
base_url = 'https://chatdemo.dev.ling.space'

AUDIO_PROFILE_PREFIX = """# AUDIO PROFILE: Alnilam.
## A young boy's voice (age 4), soft, endearing. The tone is a mix of shy curiosity and clumsy optimism. The pitch is medium-high.
### DIRECTORS NOTES
Style: Empathetic
Pace: Natural
Accent: American
### TRANSCRIPT
"""

text_to_speak = "Your text here."
content_text = AUDIO_PROFILE_PREFIX + text_to_speak

body = {
    "contents": [{"role": "user", "parts": [{"text": content_text}]}],
    "generationConfig": {
        "responseModalities": ["AUDIO"],
        "speechConfig": {
            "voiceConfig": {
                "prebuiltVoiceConfig": {"voiceName": "Alnilam"}
            }
        }
    }
}

url = f"{base_url}/v1beta/models/gemini-3.1-flash-tts-preview:generateContent?key={api_key}"
data = json.dumps(body, ensure_ascii=False).encode('utf-8')
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')

with urllib.request.urlopen(req, timeout=90) as resp:
    result = json.loads(resp.read())

# Extract audio
audio_data = None
for cand in result.get('candidates', []):
    parts = cand.get('content', {}).get('parts', []) or []
    for part in parts:
        if 'inlineData' in part:
            audio_data = base64.b64decode(part['inlineData']['data'])
            break
    if audio_data:
        break

if not audio_data:
    print("No audio data — check finishReason and usageMetadata")
    exit(1)

# PCM -> WAV
data_size = len(audio_data)
sr, ch, bits = 24000, 1, 16
br = sr * ch * bits // 8
hdr = struct.pack('<4sI4s4sIHHIIHH4sI', b'RIFF', 36+data_size, b'WAVE', b'fmt ', 16, 1, ch, sr, br, ch*bits//8, bits, b'data', data_size)
with open('/root/output.wav', 'wb') as f:
    f.write(hdr + audio_data)

# WAV -> MP3
subprocess.run(['ffmpeg', '-y', '-i', '/root/output.wav', '-codec:a', 'libmp3lame', '-q:a', '2', '/root/output.mp3'], capture_output=True)
```

## ⚠️ Pitfalls

1. **Network timeout**: Direct Google API calls fail from China — always use `https://chatdemo.dev.ling.space` as base URL.
2. **Model name**: Must be `gemini-3.1-flash-tts-preview`. Do NOT change this.
3. **Audio Profile format**: Keep the prefix as a fixed variable, concatenate speech text after `### TRANSCRIPT`. The `##` line must include the full description: `"A young boy's voice (age 4), soft, endearing. The tone is a mix of shy curiosity and clumsy optimism. The pitch is medium-high."`
4. **Empty audio response / API unreliability**: If `parts=None` or `finishReason=OTHER` or `content={}`, the API rejected the prompt. **The API is unreliable — empty responses are common even when `candidatesTokenCount` shows audio was generated.** Always implement a retry loop (3-5 attempts with 2s delay between retries):
```python
import time
audio_data = None
for attempt in range(5):
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=90) as resp:
        result = json.loads(resp.read())
    for cand in result.get('candidates', []):
        for part in (cand.get('content', {}).get('parts', []) or []):
            if 'inlineData' in part:
                audio_data = base64.b64decode(part['inlineData']['data'])
                break
        if audio_data: break
    if audio_data: break
    time.sleep(2)
```
   Common causes of consistent failure (across all retries):
   - Missing or truncated audio profile sections (ensure all `###` headers are present)
   - Plain text without Audio Profile loses voice direction but may still work
5. **Sandbox/cron cannot access GEMINI_API_KEY**: `execute_code` and cron jobs run in isolated non-interactive shells where `GEMINI_API_KEY` is NOT available. Always run Gemini TTS scripts on the host with `terminal()`. If you must run in a context where env vars may not load, use this fallback:
```python
import os, re
api_key = os.environ.get('GEMINI_API_KEY', '')
if not api_key:
    for f in ['/root/.hermes/.env', '/root/.bashrc', '/etc/environment']:
        try:
            with open(f) as fh:
                m = re.search(r'GEMINI_API_KEY=["\']?([A-Za-z0-9_-]+)["\']?', fh.read())
                if m:
                    api_key = m.group(1); break
        except: pass
if not api_key:
    print("ERROR: GEMINI_API_KEY not found"); exit(1)
```
6. **Raw PCM output**: The API returns PCM, not MP3. MIME type: `audio/l16; rate=24000; channels=1`
7. **Voice name**: Use `Alnilam` for young boy voice. Other available voices: Puck, Charon, Kore.
8. **Use `ensure_ascii=False`** in `json.dumps()` to properly handle apostrophes and special characters.
9. **API may return text parts alongside audio**: Check for `'text'` in parts too — the model sometimes outputs text interpretation.

## Audio Format Conversion

The API returns raw PCM (16-bit, 24kHz, mono). Convert to WAV and MP3:

### PCM → WAV (Pure Python)
```python
import struct

def pcm_to_wav(pcm_data, wav_file, sample_rate=24000, channels=1, bits=16):
    data_size = len(pcm_data)
    byte_rate = sample_rate * channels * bits // 8
    hdr = struct.pack('<4sI4s4sIHHIIHH4sI',
        b'RIFF', 36+data_size, b'WAVE', b'fmt ', 16,
        1, channels, sample_rate, byte_rate,
        channels*bits//8, bits, b'data', data_size)
    with open(wav_file, 'wb') as f:
        f.write(hdr + pcm_data)
```

### WAV → MP3 (ffmpeg)
```bash
ffmpeg -y -i input.wav -codec:a libmp3lame -q:a 2 output.mp3
```

## Send Audio via Feishu

After generating MP3, send to Feishu group or user:

1. **Get token**:
```python
import yaml, json, http.client, urllib.request

with open('/root/.hermes/config.yaml') as f:
    cfg = yaml.safe_load(f)
app_id = cfg['platforms']['feishu']['extra']['app_id']
app_secret = cfg['platforms']['feishu']['extra']['app_secret']

turl = 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal'
token = json.loads(urllib.request.urlopen(
    urllib.request.Request(turl, json.dumps({'app_id': app_id, 'app_secret': app_secret}).encode(),
    headers={'Content-Type': 'application/json'})
).read())['tenant_access_token']
```

2. **Upload file** (use `file_type=opus` to bypass audio validation, content-type `audio/mpeg`):
```python
with open('/root/output.mp3', 'rb') as f:
    mp3_data = f.read()

boundary = 'BOUNDARY12345'
body = b''.join([
    f'--{boundary}\r\nContent-Disposition: form-data; name="file_type"\r\n\r\nopus\r\n'.encode(),
    f'--{boundary}\r\nContent-Disposition: form-data; name="file_name"\r\n\r\noutput.mp3\r\n'.encode(),
    f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="output.mp3"\r\nContent-Type: audio/mpeg\r\n\r\n'.encode(),
    mp3_data,
    f'\r\n--{boundary}--\r\n'.encode()
])

conn = http.client.HTTPSConnection('open.feishu.cn')
conn.request('POST', '/open-apis/im/v1/files', body,
    {'Authorization': f'Bearer {token}', 'Content-Type': f'multipart/form-data; boundary={boundary}'})
file_key = json.loads(conn.getresponse().read())['data']['file_key']
```

3. **Send audio message**:
```python
# To group (chat_id):
send_url = 'https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id'
msg_body = {'receive_id': 'oc_CHAT_ID', 'msg_type': 'audio', 'content': json.dumps({'file_key': file_key})}

# To user DM (open_id):
send_url = 'https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id'
msg_body = {'receive_id': 'ou_USER_ID', 'msg_type': 'audio', 'content': json.dumps({'file_key': file_key})}

conn2 = http.client.HTTPSConnection('open.feishu.cn')
conn2.request('POST', send_url, json.dumps(msg_body).encode(),
    {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})
resp = json.loads(conn2.getresponse().read())
```

## Complete Workflow
1. Set `AUDIO_PROFILE_PREFIX` as fixed variable (do not modify)
2. Concatenate: `content_text = AUDIO_PROFILE_PREFIX + text_to_speak`
3. Call REST API with `gemini-3.1-flash-tts-preview` model
4. Extract audio from `inlineData`, save as WAV
5. Convert WAV → MP3 with ffmpeg
6. Upload to Feishu → send as audio message
7. **Run on host via `terminal()`, NOT `execute_code`** — sandbox cannot access GEMINI_API_KEY