---
name: lingos-platform
category: devops
description: Access and interact with the LingOS/Lify platform — covers cross-domain SSO authentication, Admin backend access, Lify AI agent management, debugging with AI roles, and role chat via browser automation. 20 supported roles including 李白, 爱因斯坦, 马斯克, 卢卡, etc.
trigger: "User needs to access LingOS Admin, navigate to Lify platform, manage AI agents, debug roles, or chat with Lingos AI roles via the admin panel."
---

# LingOS/Lify Platform Access & Interaction

Access the LingOS Admin backend and interact with AI roles via the Lify platform.

## URLs
- **LingOS Admin**: `https://lingos-admin-v.mo.ling.space/`
- **Lify Platform**: `https://ling-agent-admin-web.mo.ling.space/p/workspace/apps`
- **Lify App Detail**: `https://ling-agent-admin-web.mo.ling.space/p/workspace/apps/detail/{app_id}`

## Authentication Flow (Critical — applies to ALL platform access)

1. **Always login via LingOS Admin first** — Lify uses cross-domain SSO and requires an active LingOS session
2. Login with account/password on LingOS login page (select **"Log in"** tab, NOT "Sign up")
3. **Navigate directly** to Lify URL: `https://ling-agent-admin-web.mo.ling.space/p/workspace/apps`

### ⚠️ Cross-Domain SSO Gotcha
- The Lify link in sidebar has `target="_blank"` — browser session does NOT follow to new tab
- If you navigate to Lify directly without LingOS session: "请关闭页面从 Lingos 重新登录"
- If session expires on Lify: go back to LingOS login → re-authenticate → re-navigate to Lify
- Auth token stored in `localStorage.console_token` and `localStorage.user`
- Account info: `{ "isLogin": true, "user": { "token": "B_...", "username": "..." } }`

## Section 1: Platform Navigation & App Management (from lingos-lify-web-access)

### Search for an App/Role
1. Navigate to Lify workspace apps page
2. Type search term in "搜索应用名称" textbox
3. Press Enter or wait for results
4. Click the app name link (NOT the "详情" button — click the name hyperlink directly)

### List All Roles (Paginated)
- App list is paginated — 10 items per page, typically 6 pages (~60 apps)
- Page buttons are `<li tabindex>` elements with text '1', '2', '3', etc.
- Use `browser_console` JS to iterate pages programmatically:
```js
const rows = document.querySelectorAll('table tbody tr');
[...rows].map(r => { const a = r.querySelector('a'); return a ? a.textContent.trim() : ''; }).filter(Boolean);
```

### Role Name Normalization Patterns
Strip prefixes/suffixes to group variants:
- `【小方角色】-lify-{name}-1.0-online` → **{name}**
- `【小方角色】-lify-V版-{name}-1.0-online` → **{name}** (V版 variant)
- `【小方角色】-{name}_Lify_{version}_online` → **{name}**
- `【VIP环境】MC {name}_Lify_{version}_online` → **{name}** (VIP/MC variant)
- Common suffixes to strip: `-1.0-online`, `-V版`, `-白名单`, `_Lify_*`, `_online`, `-lify-*`

## Section 2: Role Chat & Debugging (from lingos-role-chat)

### Supported 20 Roles
李白、狮子老爸、爱因斯坦、史蒂夫、马斯克、卢卡、海蒂、苏东坡、达尔文、哪吒、方舟姐姐、朵咪、3D绘画喵、曹文、席瑞、福尔摩斯、白泽、yummy、DM小巴啦、Santa

### Debug/Chat Workflow
1. Enter app detail page: `https://ling-agent-admin-web.mo.ling.space/p/workspace/apps/detail/{app_id}`
2. Page has two panels: left = prompt/config editor, right = "调试与预览" chat area
3. **⚠️ Set parameters FIRST** (required before sending, otherwise no response):
   - Click the **second icon button** (gear/settings) in preview panel header (top-right of right panel)
   - In "参数设置" dialog, select **"闲聊"** from the top dropdown
   - This auto-fills all variables: role, limit, feature, skills, thinking, resource, sys_cmd, mode, prologue_prefix, location, tools_description
   - Click **"确定"** to apply and close
4. **Send message via JS dispatch** (clicking send button or pressing Enter typically fails):
```javascript
var chatInp = document.querySelector('input[placeholder="输入消息..."]');
chatInp.value = '你的消息内容';
chatInp.dispatchEvent(new Event('input', {bubbles: true}));
chatInp.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}));
```
5. Wait 15-25s for AI response
6. Extract response from end of `document.body.innerText`:
```javascript
var txt = document.body.innerText;
txt.substring(txt.length - 1000);
```

### Troubleshooting
- If search box has残留 text: clear it first before typing
- If multiple search results (V版, 白名单, online variants): pick the main version (usually without V版/白名单)
- If page shows "请关闭页面从 Lingos 重新登录": return to LingOS → login → navigate to Lify directly
- Some roles call tools (e.g., get_current_time) — response shows tool call status
- If no reply after 25s: wait another 10s and retry extraction
