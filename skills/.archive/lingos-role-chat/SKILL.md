---
name: lingos-role-chat
description: Chat with Lingos AI roles via Lify admin panel. 20 supported roles including 李白, 狮子老爸, 爱因斯坦, 史蒂夫, 马斯克, 卢卡, 海蒂, 苏东坡, 达尔文, 哪吒, 方舟姐姐, 朵咪, 3D绘画喵, 曹文, 席瑞, 福尔摩斯, 白泽, yummy, DM小巴啦, Santa.
tags: ["lingos", "lify", "chat", "ai-roles"]
---

# Lingos 角色对话 Skill

## 支持的 20 个角色

李白、狮子老爸、爱因斯坦、史蒂夫、马斯克、卢卡、海蒂、苏东坡、达尔文、哪吒、方舟姐姐、朵咪、3D绘画喵、曹文、席瑞、福尔摩斯、白泽、yummy、DM小巴啦、Santa

## 对话流程

### 1. 登录 LingOS Admin
- 导航到 `https://lingos-admin-v.mo.ling.space/`
- 用户名: `robot_hermes`，密码: `robot_hermes@L1v3Gof;`
- 如果已登录（localStorage 有 console_token），跳过

### 2. 进入 Lify 平台
- 点击左侧栏 "Lify" 链接
- 或直接导航 `https://ling-agent-admin-web.mo.ling.space/p/workspace/apps`

### 3. 搜索角色
- 在搜索框输入角色名（如 "李白"）
- 可能出现多个变体（V版、白名单、online 等），选主版本（通常是不带 V版/白名单 的）

### 4. 进入角色详情
- 点击该行的 "详情" 按钮
- 进入编排页面，右侧有 "调试与预览" 区域

### 5. 设置对话参数（⚠️ 必须先设置，否则发送消息无响应）
- 进入角色详情页后，点击右侧预览面板右上角的**第二个图标按钮**（齿轮/设置图标），打开"参数设置"弹窗
- 弹窗顶部有一个下拉框，包含预设选项："聊天任务"、"闲聊"
- **选择"闲聊"**，系统会自动填充所有变量字段（role, limit, feature, skills, thinking, resource, sys_cmd, mode, prologue_prefix, location, tools_description）
- 点击底部 **"确定"** 按钮关闭弹窗并应用参数
- 变量字段列表：role、limit、feature、skills、thinking、resource、sys_cmd、mode、prologue_prefix、location、tools_description
- 底部还有"调试设置"→"用户ID"输入框，默认 0 即可

### 6. 发送对话（⚠️ 必须用 JS 方式，点击按钮/Enter 均无效）
- 使用 `browser_console` 执行以下 JavaScript：
```javascript
var chatInp = document.querySelector('input[placeholder="输入消息..."]');
chatInp.value = '你的消息内容';
chatInp.dispatchEvent(new Event('input', {bubbles: true}));
chatInp.dispatchEvent(new Event('change', {bubbles: true}));
// 然后用 browser_press Enter 发送
```
- 或者用完整 JS 一次性发送：
```javascript
var chatInp = document.querySelector('input[placeholder="输入消息..."]');
chatInp.value = '你的消息内容';
chatInp.dispatchEvent(new Event('input', {bubbles: true}));
chatInp.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}));
chatInp.dispatchEvent(new KeyboardEvent('keyup', {key: 'Enter', bubbles: true}));
```

### 7. 等待回复
- 等待 15-25 秒让 AI 回复（可能调用工具如 get_current_time）
- 从 `document.body.innerText` 末尾提取回复（页面没有独立的 chat-message-list 容器）：
```javascript
var txt = document.body.innerText;
txt.substring(txt.length - 1000);
```
- 回复格式：用户消息后面紧跟 "AI" 或角色名开头的回复内容
- 如果回复未出现，再等待 10 秒重试

### 7. 返回结果
- 整理为用户消息 + AI 回复的格式返回

## 注意事项
- Lify 不支持独立登录，必须从 Lingos 点击跳转或通过 cookie/localStorage token 传递
- **直接导航**到 `https://ling-agent-admin-web.mo.ling.space/p/workspace/apps` 比点击侧边栏 Lify 链接更稳定
- 如果页面提示"请关闭页面从 Lingos 重新登录"，需要先回 Lingos 登录再跳转
- 部分角色可能调用了工具（如 get_current_time），回复中会显示工具调用状态
- 如果搜索框有残留文本，先清空再输入
- 搜索结果中可能有多个变体（V版、白名单、online 等），选主版本（通常是不带 V版/白名单 的）
- 点击应用名称链接进入详情页（不要点"详情"按钮，点名称超链接）