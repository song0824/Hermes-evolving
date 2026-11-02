---
name: lingos-lify-web-access
category: devops
description: Access LingOS Admin backend and navigate to Lify platform for AI agent management, debugging, and chat. Covers cross-domain SSO authentication flow and common tasks.
tags: [lingos, lify, browser, web-login, sso]
---

# LingOS Admin & Lify Web Platform Access

Access the LingOS Admin backend and navigate to the Lify platform for AI agent management and debugging.

## URLs
- **LingOS Admin**: `https://lingos-admin-v.mo.ling.space/`
- **Lify Platform**: `https://ling-agent-admin-web.mo.ling.space/p/workspace/apps`
- **Lify App Detail**: `https://ling-agent-admin-web.mo.ling.space/p/workspace/apps/detail/{app_id}`

## Authentication Flow (Critical)

1. **Always login via LingOS Admin first** — Lify uses cross-domain SSO and requires an active LingOS session
2. Login with account/password on the LingOS login page (Sign up / Log in tabs — use "Log in")
3. Click "Lify" link in the left sidebar

### ⚠️ Cross-Domain SSO Gotcha
- The Lify link has `target="_blank"` — the browser session does NOT follow it to a new tab
- **Solution**: After logging into LingOS, navigate directly to `https://ling-agent-admin-web.mo.ling.space/p/workspace/apps`
- If you navigate to Lify directly without LingOS session, you'll see: "请关闭页面从 Lingos 重新登录"
- If session expires on Lify, go back to LingOS login and re-authenticate, then re-navigate to Lify

## Authentication Details
- Login page has two tabs: "Sign up" and "Log in" — always select "Log in"
- Auth token stored in `localStorage.console_token` and `localStorage.user`
- Account info: `{ "isLogin": true, "user": { "token": "B_...", "username": "..." } }`

## Common Tasks

### Search for an App/Role
1. Navigate to `https://ling-agent-admin-web.mo.ling.space/p/workspace/apps`
2. Type search term in the "搜索应用名称" textbox
3. Press Enter or wait for results
4. Click "详情" button for the desired app

### List All Roles (Paginated)
- The app list is paginated — 10 items per page, typically 6 pages (~60 apps)
- Page buttons are `<li tabindex>` elements with text '1', '2', '3', etc.
- Click a page number, wait ~1.5s for data to load, then extract app names from `table tbody tr a`
- Use `browser_console` with JS to iterate pages programmatically:
```js
const rows = document.querySelectorAll('table tbody tr');
[...rows].map(r => { const a = r.querySelector('a'); return a ? a.textContent.trim() : ''; }).filter(Boolean);
```

### Role Name Normalization Patterns
App names follow these patterns — strip prefixes/suffixes to group variants:
- `【小方角色】-lify-{name}-1.0-online` → **{name}**
- `【小方角色】-lify-V版-{name}-1.0-online` → **{name}** (V版 variant)
- `【小方角色】-{name}_Lify_{version}_online` → **{name}**
- `【小方角色】-{name}-lify-{version}-online` → **{name}**
- `【VIP环境】MC {name}_Lify_{version}_online` → **{name}** (VIP/MC variant)
- `【小方机角色】lify-{name}-{model}_{env}_online` → **{name}**
- `【海外卢卡】-Luka` → **卢卡** (localized name)
- Common suffixes to strip: `-1.0-online`, `-V版`, `-白名单`, `_Lify_*`, `_online`, `-lify-*`

### Debug/Chat with an Agent
1. Enter the app detail page via URL: `https://ling-agent-admin-web.mo.ling.space/p/workspace/apps/detail/{app_id}`
   - The "详情" button navigates here; you can also construct the URL directly from the app ID
2. The page has two panels: left = prompt/config editor, right = "调试与预览" chat area
3. **⚠️ Set parameters first** (required before sending, otherwise no response):
   - Click the second icon button (gear/settings) in the preview panel header (top-right of right panel)
   - In the "参数设置" dialog, use the dropdown at the top to select **"闲聊"**
   - This auto-fills all variables: role, limit, feature, skills, thinking, resource, sys_cmd, mode, prologue_prefix, location, tools_description
   - Click "确定" to apply and close
4. Find the chat input (placeholder: "输入消息...")
5. **Must use JS dispatch** to send — clicking the send button or pressing Enter typically fails:
```javascript
var chatInp = document.querySelector('input[placeholder="输入消息..."]');
chatInp.value = 'message';
chatInp.dispatchEvent(new Event('input', {bubbles: true}));
chatInp.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}));
```
5. Wait 15-25s for AI response
6. Extract response from `document.body.innerText` (last ~1000 chars):
```javascript
var txt = document.body.innerText;
txt.substring(txt.length - 1000);
```

## Session Persistence
For persistent cookie management across browser sessions, see the `web-login-session-management` skill for Playwright storage_state patterns.

## Browser Tool Fallback
If asked to use `opencli browser` but the Browser Bridge extension isn't connected (`opencli doctor` shows "Extension: not connected"), fall back to built-in `browser_navigate`, `browser_type`, `browser_click`, `browser_press`, `browser_snapshot` tools instead.
