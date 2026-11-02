---
name: browser-automation
category: web
description: Browser automation patterns for headless environments — covers authentication/QR login flows, Chrome extension loading, video analysis via browser+vision, anti-bot detection bypass, CDP connections, virtual display setup, and storage state persistence.
trigger: "User needs to automate browser interactions that are blocked by anti-bot detection, headless restrictions, or require extension loading. Covers QR code login flows, Chrome extension loading in headless/server environments, video analysis via browser playback + vision AI, cookie/session persistence, and OpenCLI browser integration."
---

# Browser Automation in Headless/Server Environments

Shared patterns for browser automation when headless mode, anti-bot detection, or server constraints block standard approaches. Three major use cases are covered as labeled sections below.

## Shared Core Patterns (apply to ALL use cases)

### Anti-Bot Detection & CDP Fallback

When sites block headless browsers (common with login/QR flows, extension-required sites):

1. **Detection signs**: `error_code: 2046`, "暂不支持此操作", page stays on login despite successful scan, elements missing from snapshots
2. **First fix**: Enhanced anti-detection scripts in `add_init_script` (hide `navigator.webdriver`, fake plugins, fake chrome runtime, fake WebGL)
3. **Nuclear fix**: Connect to a **real Chrome instance** via CDP instead of launching headless:

```python
browser = pw.chromium.connect_over_cdp("http://localhost:9224")
context = browser.contexts[0]
```

CDP bypasses most headless detection because you're using a real browser with real extensions and real user data.

### Virtual Desktop Setup (required for headed Chromium)

- **Google Chrome** blocks `--load-extension` entirely
- **headless/headless=new** mode does not support `--load-extension`
- **Chromium** supports `--load-extension` but requires a display server

```bash
# 1. Install desktop environment
apt-get install -y xfce4 xfce4-goodies dbus-x11

# 2. Start Xvfb virtual display
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99

# 3. Launch Chromium with extension
/root/.cache/ms-playwright/chromium-*/chrome-linux64/chrome \
  --no-sandbox --disable-gpu \
  --disable-extensions-except=/path/to/extension \
  --load-extension=/path/to/extension \
  --user-data-dir=/root/chrome-profile-ext \
  --remote-debugging-port=9224
```

Key flags:
- `--disable-extensions-except=<path>` — only load specified extension
- `--load-extension=<path>` — load unpacked extension directory
- `--no-sandbox` — required for root user
- **Do NOT use Google Chrome** (`/usr/bin/google-chrome`) — it ignores `--load-extension`

### Cookie Persistence via Storage State

Never launch a fresh browser per request. Use Playwright's `storage_state` to persist and reload cookies:

```python
from playwright.sync_api import sync_playwright
from pathlib import Path
import json

STORAGE_PATH = Path.home() / ".hermes" / "cache" / "<site>_storage_state.json"

context_opts = {"viewport": {"width": 1920, "height": 1080}}
if STORAGE_PATH.exists():
    context_opts["storage_state"] = str(STORAGE_PATH)

context = browser.new_context(**context_opts)
# ... do login work ...
state = context.storage_state()
with open(STORAGE_PATH, "w") as f:
    json.dump(state, f, indent=2)
```

### Extension Verification via CDP

```bash
curl -s http://localhost:9224/json/list | python3 -m json.tool
```

Look for targets with `"type": "service_worker"` and `"url": "chrome-extension://<ID>/..."`.

### OpenCLI Browser Integration

Extension daemon listens on `127.0.0.1:19825`. Remote connections require SSH tunnel:
```bash
ssh -L 19825:localhost:19825 root@<server-ip>
```

After loading extension in Chromium, restart daemon:
```bash
opencli daemon restart && opencli doctor
```

**opencli browser commands**:
```bash
opencli doctor                              # Check connection status
opencli browser <session> open <URL>         # Open page
opencli browser <session> state              # View element index
opencli browser <session> screenshot [path]  # Screenshot
opencli browser <session> click N            # Click element [N]
opencli browser <session> fill N 'text'      # Fill form
opencli browser <session> extract            # Extract page as Markdown
opencli browser <session> console            # View console logs
opencli browser <session> close              # Close tab
```

If extension fails to connect, fall back to Playwright (`browser_navigate` + `browser_console` + `browser_vision`).

**opencli douyin adapter limitation**: The `opencli douyin` adapter targets `creator.douyin.com` (creator platform), NOT `fxg.jinritemai.com` (merchant backend). For merchant backend via opencli, use `opencli browser fxg <command>` generic browser mode only.

### Shared Pitfalls

- **Google Chrome ignores `--load-extension`**: The binary has this flag hardcoded as blocked. Use Chromium instead.
- **Playwright Chromium needs `DISPLAY`**: Even with `headless=False`, needs `$DISPLAY` set to an X server. Set `os.environ['DISPLAY'] = ':99'` before launch.
- **headless mode blocks extensions**: Neither `--headless` nor `--headless=new` supports loading extensions.
- **CRX download from google.com times out**: In Chinese server environments, use crxsoso.com mirror or browser-based download.
- **`unzip` warning on CRX files**: "extra bytes at beginning" is the CRX signature — extraction still works.
- **Extension ID changes on load**: Unpacked extensions get a different ID than the Chrome Web Store version. Check CDP targets to find the actual ID.
- **`networkidle` timeout**: `page.goto(..., wait_until="networkidle")` hangs on complex pages. Use `wait_until="domcontentloaded"` instead.
- **Cookie domain mismatch**: Login cookies often need `.domain.com` (leading dot) to work across subdomains. Let the browser set cookies naturally through the login flow, then save `storage_state`.
- **Port 10080 is ERR_UNSAFE_PORT in browser**: Chrome/Playwright blocks port 10080. Use `curl` or Python `requests` via terminal instead.

---

## Section 1: Authentication & QR Login Flows

**Trigger**: User needs QR code login, session persistence, or bypassing anti-bot detection on sites like 抖店 (jinritemai.com).

### Core Pattern: Same-Instance Navigation Rule

**Critical**: Never restart browser between login and target page access. The session is tied to the browser instance.
- Correct: Launch → login → navigate to target → save state → close (all in same instance)
- Incorrect: Launch → generate QR → close → launch new with cookies → navigate (session never established)

### QR Code Login Monitoring

QR login flows use polling endpoints. Monitor network responses to detect state changes:

```python
def on_response(response):
    if "check_qrconnect" in response.url:
        body = response.json()
        status = body.get("data", {}).get("status", "0")
        # status "1" = waiting, "2" = scanned, "3"/"4" = logged in
        # error_code 2046 = security block (headless detected)
    if "check_login" in response.url:
        body = response.json()
        has_login = body.get("has_login", False)
```

### 抖店 (Douyin Store) Specific Patterns

- **Login URL**: `https://fxg.jinritemai.com/login/common?channel=zhaoshang`
  - The `?channel=zhaoshang` parameter is **MANDATORY**. Without it, user gets redirected to wrong login page (抖音APP instead of 抖店APP).
- **Order list URL**: `https://fxg.jinritemai.com/ffa/morder/order/list`
- **QR mode switcher**: `document.querySelector('.login-switcher--cell').click()`
  - browser_snapshot often misses this element — use `browser_console` JS execution directly
- **Error 2046**: `{\"error_code\":2046,\"description\":\"为保证账号安全，暂不支持此操作\"}` — server-side headless detection. Solution: CDP connection to real Chrome.
- **Cookie names**: `sessionid`, `sid_tt`
- **Storage state path**: `~/.hermes/cache/fxg_storage_state.json`

### User Communication Preferences

- **Always send QR code image** immediately with the response (MEDIA: path).
- **Minimal output** — user expects only final results, no process explanation.
- **QR refresh at :00 second marks** when requested. QR codes expire in 2-5 minutes.
- **After scan**: do NOT auto-navigate. Stay on current page, screenshot to verify, wait for user's next command.
- **Never silently retry** when user expresses frustration — acknowledge failure, explain root cause, propose alternative.

### Verification

After login, verify by:
1. Check URL no longer contains "login"
2. Check page title changed from "登录" to actual app title
3. Check cookies contain session tokens (`sessionid`, `sid_tt`, etc.)
4. Navigate to a protected page and confirm no redirect to login

### VPN Tunnel Workaround for Error 2046

When headless login is blocked on cloud servers, route browser traffic through user's residential/office IP via OpenVPN. See `openvpn-client-setup` skill for client configuration.

---

## Section 2: Chrome Extension Loading

**Trigger**: User needs to load Chrome extensions in server/headless environments.

### CRX Download

The Google CRX download API (`clients2.google.com`) is often unreachable from Chinese servers. Use browser-based download:

```bash
# Navigate to crxsoso.com mirror in browser, click download button
# Extension saves to /root/Downloads/ as .crdownload → rename to .crx
```

Alternative mirrors (may be blocked):
- `https://www.crxsoso.com/webstore/detail/<EXTENSION_ID>`
- `https://chrome-extension-downloader.com/`
- `https://crxextractor.com/`

### CRX Extraction

```bash
unzip -o extension.crx -d /path/to/extension-dir/
# Warning about "extra bytes at beginning" is normal — CRX header
```

Verify manifest: `cat /path/to/extension-dir/manifest.json`

---

## Section 3: Video Analysis via Browser + Vision

**Trigger**: User shares a video URL (YouTube, Bilibili, etc.) and needs content extraction when transcripts are unavailable, subtitles are burned-in, or video download is blocked by anti-bot measures.

### Workflow

1. **Check for transcript/subtitle availability** first:
   - YouTube: `curl "https://www.youtube.com/api/timedtext?v=VIDEO_ID&lang=en"`
   - Bilibili: `curl "https://api.bilibili.com/x/player/v2?bvid=BVxxx&cid=CID"` — check `data.subtitle.subtitles` array
   - If subtitles exist → extract and use them. If not → proceed to vision approach.

2. **Play video in browser and extract frames at key timestamps**:

```javascript
// In browser_console — seek to timestamp (seconds)
var v = document.querySelector('video');
v.currentTime = 60;
v.play();
```

```bash
# Wait for rendering (5+ seconds)
sleep 5
```

```javascript
// Pause and verify position
var v = document.querySelector('video');
v.pause();
Math.round(v.currentTime) + 's'
```

```python
# Analyze the frame
browser_vision(question="Describe EVERYTHING visible: text, subtitles, UI elements, diagrams, numbers. Be extremely detailed.")
```

3. **Sample strategy**:
   - For rule/tutorial videos: Seek every 60-120 seconds
   - For visual content: Seek every 30 seconds
   - Total frames: 5-10 frames is usually sufficient for a 10-minute video

### Platform-Specific Patterns

#### Bilibili
- **API endpoints that work** (no auth):
  - Video info: `https://api.bilibili.com/x/web-interface/view?bvid=BVxxx`
  - Subtitle check: `https://api.bilibili.com/x/player/v2?bvid=BVxxx&cid=CID`
  - Tags: `https://api.bilibili.com/x/tag/archive/tags?bvid=BVxxx`
  - Danmaku: `https://comment.bilibili.com/{CID}.xml` (zlib compressed)
- **Anti-bot**: `yt-dlp` and `curl` get HTTP 412. Video **must** be analyzed via browser playback.
- Login popups may appear after ~30s of playback — navigate to the URL again to reset.
- Search results on Baidu/Sogou trigger CAPTCHAs — use Bilibili's own search instead.

#### YouTube
- Use `youtube-content` skill first (transcript API)
- If no transcript, fall back to browser + vision approach
- yt-dlp usually works; if not, use browser approach

### Video Pitfalls

- **Don't wait for video to play naturally** — always use `v.currentTime` to seek
- **Don't call browser_vision immediately after seeking** — the video needs 3-5 seconds to render the frame
- **JavaScript redeclaration errors** — use `var v =` not `const v =` in browser_console since declarations persist
- **Video element not found** — some players use `<iframe>`; navigate directly to the embed URL
- **Don't retry yt-dlp multiple times** — if it fails with 412 once, switch to browser approach immediately.
