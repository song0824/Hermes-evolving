# 抖店 (fxg.jinritemai.com) QR Login Details

## URLs
- Login: `https://fxg.jinritemai.com/login/common?channel=zhaoshang`
- Order list: `https://fxg.jinritemai.com/ffa/morder/order/list`

## QR Switch Selector
- CSS: `.login-switcher--cell`
- This element toggles between phone/email login and QR code login

## Login Detection
- Success: URL changes away from `/login/` path
- Failure: URL remains at `/login/common?channel=zhaoshang`

## Cookie Behavior
- Login session cookies: `sessionid`, `sid_tt`, `sid_guard`, `sessionid_ss`
- These are set AFTER successful QR scan, not present on login page
- `passport_csrf_token` and `passport_csrf_token_default` exist pre-login but are NOT session cookies
- Device fingerprint changes may invalidate session (IP/browser switch causes re-login)

## Anti-Bot Notes
- Site uses `secsdk` for bot detection
- `s_v_web_id` cookie is the device fingerprint
- `x-web-secsdk-uid` is another tracking cookie
- Standard Playwright without stealth plugins will be detected
- Use `--disable-blink-features=AutomationControlled` and inject `navigator.webdriver = undefined`

## Common Issues
1. **白屏 after scan**: Page redirects but content doesn't load. Use `page.goto()` to re-navigate after detecting URL change.
2. **Cookie count stays at ~13**: This means no login session was established. Login cookies (sessionid, sid_tt) should push count to 20+.
3. **Storage state file has cookies but new browser can't login**: Device fingerprint (`s_v_web_id`) may not match. The browser instance that generated the QR must be the same one that receives the login callback.
