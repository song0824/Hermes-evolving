---
name: opencli-xiaohongshu
category: social-media
description: Scrape Xiaohongshu (小红书) data using opencli — capabilities, requirements, and constraints.
trigger: "User asks to scrape, search, or monitor Xiaohongshu (小红书) content, notes, comments, or creator data"
---

# OpenCLI Xiaohongshu (小红书) Scraping

## Available Commands

`opencli xiaohongshu <command>`:

| Command | Requires | Description |
|---------|----------|-------------|
| `search <query>` | cookie | Search notes by keyword. Output: rank, title, author, likes, published_at, url |
| `note <note_id>` | cookie | Get note body text and interaction data |
| `user <profile_url>` | cookie | Get public notes from a user profile |
| `creator-profile` | cookie | Creator account info (followers, following, likes, level) |
| `creator-notes` | cookie | Creator's note list + per-note data (title/date/views/likes/saves/comments) |
| `creator-notes-summary` | cookie | Recent notes batch summary |
| `creator-note-detail` | cookie | Single note detail (audience profile, trends) |
| `creator-stats` | cookie | Creator data overview (daily trends) |
| `comments <note_id>` | cookie | Note comments (supports nested replies) |
| `download <note_id>` | cookie | Download images/videos from a note |
| `feed` | intercept | Homepage recommendation feed (via Pinia Store Action) |
| `publish` | cookie | Publish image/text notes (creator center UI automation) |
| `notifications` | intercept | Notifications (mentions/likes/connections) |

Usage: `opencli xiaohongshu search "关键词" --limit 20 -f json`

## Critical Constraints

### 1. Browser Bridge Extension Required
opencli's xiaohongshu adapter **requires the Chrome Browser Bridge extension** to be connected. Without it:
```
error: BROWSER_CONNECT — Browser Bridge extension not connected
```

Fix:
1. Download extension: https://github.com/jackwener/opencli/releases
2. Open chrome://extensions → Developer Mode → Load unpacked
3. Select extension folder → ensure it connects to opencli daemon
4. Verify: `opencli doctor` should show `[OK] Extension: connected`

### 2. Server/Headless Environment Limitations
- **Direct XHS web access blocked**: `IP at risk. Switch to a secure network and retry.` — XHS aggressively blocks server/datacenter IPs
- **Login required**: Most XHS pages redirect to login/captcha
- **Search engines useless**: Bing/Google/DuckDuckGo/Sogou do NOT effectively index XHS content — searching `小方机 site:xiaohongshu.com` returns 0 relevant results

### 2b. Server-Side Chrome + Extension Setup (Verified Working)
To run opencli Browser Bridge on a headless server (no local desktop Chrome):

```bash
# 1. Ensure Xvfb is installed and running
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99

# 2. Unzip the extension (provided by user or downloaded from GitHub releases)
unzip -o opencli-extension-v1.0.15.zip -d ~/.opencli/extension

# 3. Kill old Chrome, clean profile, launch fresh
pkill -9 -f google-chrome; rm -rf /tmp/opencli-chrome-profile
google-chrome --no-first-run --no-default-browser-check --disable-gpu \
  --no-sandbox --disable-dev-shm-usage --enable-extensions \
  --load-extension=~/.opencli/extension \
  --remote-debugging-port=9222 --remote-allow-origins=* \
  --user-data-dir=/tmp/opencli-chrome-profile about:blank &

# 4. Restart daemon and verify
opencli daemon restart
sleep 2
opencli doctor  # Should show [OK] Extension: connected
```

**Key findings**:
- **Chrome DOES support `--load-extension`** when running with a virtual display (Xvfb). The restriction only applies to `--headless` and `--headless=new` modes.
- **`--remote-allow-origins=*`** is required for CDP WebSocket connections from the daemon.
- Clean profile (`rm -rf /tmp/opencli-chrome-profile`) is needed if extension failed to load on first attempt.
- `opencli daemon restart` helps the daemon pick up the newly connected extension.

### 3. Cookie Requirement
Most xiaohongshu commands require a valid `cookie` parameter or pre-configured browser session. Get cookie from logged-in browser DevTools.

## Workarounds

| Situation | Solution |
|-----------|----------|
| Need to search XHS from server | Install Browser Bridge extension on a desktop Chrome, or provide XHS login cookie |
| Monitoring/sentiment analysis | Use SLS logs if XHS-related traffic is logged, or database queries for internal task data |
| One-off data grab | User provides cookie → `opencli xiaohongshu search "关键词" --limit 50 -f json` |

## OpenCLI Browser Universal Mode

Beyond site-specific adapters, opencli has a **universal browser mode** that works with ANY website:

```bash
# Initialize a browser session
opencli browser <session_name> open "https://example.com"

# Check page state (elements with [N] indices)
opencli browser <session_name> state

# Click element by index
opencli browser <session_name> click N

# Type text into element
opencli browser <session_name> type N "text"

# Take screenshot
opencli browser <session_name> screenshot /tmp/output.png

# Execute JavaScript
opencli browser <session_name> eval "document.cookie"

# Close session
opencli browser <session_name> close
```

Session names are arbitrary strings (e.g., `fxg`, `xhs`, `work`). Reuse the same name to maintain tab/state across calls.

## Douyin Store (抖店/fxg) Order Extraction

For Douyin Store merchant backend (`fxg.jinritemai.com`), the following API endpoints work with valid cookies:

| API | Method | Purpose |
|-----|--------|---------|
| `/api/order/orderDetail?order_id=<id>` | GET | Order details (status, product, logistics) |
| `/api/order/orderDetail` | GET | Order details with masked receiver info |

**Important**: Phone numbers and detailed addresses are **encrypted/masked** (e.g., `1**********`, `***********`). To get plaintext, you must use the Douyin Open Platform API (`order/getTradeCipher`) which requires app_key/app_secret and has daily quotas (~290 for sub-accounts, 10k-200k+ for main accounts).

**Working endpoints confirmed** (as of 2025-05-20):
- `POST /ffa/api/order/list` — returns HTML page (SPA entry point)
- `GET /api/order/orderDetail?order_id=<id>` — returns JSON with order data
- `GET /api/order/detail?order_id=<id>` — triggers captcha verification

See `references/douyin-fxg-order-api.md` for full API structure and response format.
See `references/douyin-fxg-ui-scraping.md` for UI-based scraping workflow and limitations.

## Pitfalls
- Never try browser_navigate to xiaohongshu.com from server — always blocked by IP risk
- Never try search engines for XHS content — returns irrelevant results (dictionary definitions, etc.)
- **Extension disconnected → commands silently timeout**: When `opencli doctor` shows `Extension: disconnected`, all xiaohongshu commands will hang until timeout (30s+) with no useful error. Always verify extension is connected FIRST.
- opencli daemon must be running: `opencli daemon status`
- **Extension disconnected after Chrome restart**: Run `opencli daemon restart` then reopen Chrome with `--load-extension`. Verify: `opencli doctor` should show `Extension: connected` with profile name.
- Extension must be actively connected — not just installed. Check: `opencli profile list` should show connected profiles.
- All direct access methods confirmed blocked: curl, browser_navigate, Python xhs library, third-party APIs/scraper sites (all get IP risk error 300012)
- Update opencli regularly: `npm install -g @jackwener/opencli` (verified working: v1.7.22)
- **Chrome `--load-extension` only works with virtual display (Xvfb)**: `google-chrome --headless` and `--headless=new` silently ignore `--load-extension`. Use Xvfb (`DISPLAY=:99`) for headless servers: `google-chrome --no-sandbox --load-extension=... --remote-allow-origins=*` with `DISPLAY=:99`. Verify via `opencli doctor` showing `Extension: connected`.
- **Extension loads but not in CDP targets?** Clean the Chrome profile: `rm -rf /tmp/opencli-chrome-profile` and restart Chrome with a fresh profile.
- **Terminal hangs with Chrome**: Zombie Chrome processes can cause all subsequent `terminal` commands to return `[Command interrupted]` (SIGINT). If this happens, kill Chrome processes (`pkill -9 -f chrome`) and start fresh. Avoid running Chrome + `sleep` in the same command as it can cause cascading timeouts.
- Chrome processes on the server can hang and block terminal. If stuck, try `pkill -9 -f google-chrome` but be prepared for the terminal to become unresponsive — start a fresh session if needed.
