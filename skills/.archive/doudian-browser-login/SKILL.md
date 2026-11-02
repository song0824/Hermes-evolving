---
name: doudian-browser-login
description: 抖店后台浏览器登录流程 — 正确的 URL、切换到抖店APP扫码模式、订单管理跳转。
trigger: 需要浏览器自动化登录抖店后台、查询抖店订单、抓取抖店数据
---

## 抖店后台浏览器登录流程

### 1. 正确登录 URL
```
https://fxg.jinritemai.com/login/common?channel=zhaoshang
```
⚠️ **必须带 `?channel=zhaoshang` 参数**，否则会被重定向到普通登录页（只有抖音APP扫码，没有抖店APP选项）。

### 2. 切换到抖店APP扫码模式
默认页面是「手机号+验证码」登录。需要点击右侧的二维码切换图标切换到扫码模式：

```javascript
document.querySelector('.login-switcher--cell').click()
```

⚠️ **重要实操经验**：
- 该元素是 76x76px 的绝对定位 div，背景图为二维码图标
- **可访问性树快照（browser_snapshot）经常无法捕获此元素**，不要依赖 `browser_click` 点击快照 ref
- **可靠做法**：用 `browser_console` 直接执行 JS `document.querySelector('.login-switcher--cell').click()`
- 页面上有多处可点击元素（手机/邮箱切换 tab），容易点错。`@e39`/`@e40` 是手机/邮箱 tab，不是二维码切换按钮

切换成功后：
- 页面显示**抖店蓝色 logo** 的二维码（不是抖音黑色logo）
- 用户用**抖店APP**扫码登录
- ⚠️ 页面部分中文可能显示为方框（字体缺失），不影响二维码功能

### 3. URL 区别

| URL | 扫码方式 | 二维码Logo |
|---|---|---|
| `fxg.jinritemai.com/login/common`（无参数） | 抖音APP | 黑色（抖音音符） |
| `fxg.jinritemai.com/login/common?channel=zhaoshang` | 抖店APP | 蓝色（抖店） |

### 3b. CRX 扩展文件下载（已验证）

- Google Chrome Web Store (`clients2.google.com`)：服务器直连超时
- 各 CRX 镜像源均失败（404/不可达）
- **可行方案**：通过 `browser_navigate` 打开 `https://www.crxsoso.com/webstore/detail/ildkmabpimmkaediidaifkhjpohdnifk`，点击绿色'安装到浏览器'按钮旁边的白色下箭头按钮，文件下载到 `/root/Downloads/`，扩展名为 `.crdownload`，完成后重命名为 `.crx`
- 解压：`unzip -o file.crx -d /path/to/extension-dir/`（CRX3 格式，报'extra bytes'警告但能正常解压）

### 3c. opencli 扩展服务器端加载（已验证）

**关键问题**：`google-chrome`（Google Chrome 稳定版）**完全禁止** `--load-extension` 参数（硬编码拦截，日志：`--load-extension is not allowed in Google Chrome, ignoring.`）。`--headless`/`--headless=new` 模式同样不支持加载扩展。

**可行方案**：使用 **Chromium**（非 Google Chrome）+ **Xvfb 虚拟显示**

```bash
# 1. 虚拟桌面
apt-get install -y xfce4 xfce4-goodies dbus-x11
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99

# 2. Playwright Chromium 加载扩展
/root/.cache/ms-playwright/chromium-*/chrome-linux64/chrome \
  --no-sandbox --disable-gpu \
  --disable-extensions-except=/root/opencli-extension \
  --load-extension=/root/opencli-extension \
  --user-data-dir=/root/chrome-profile-ext \
  --remote-debugging-port=9224 &

# 3. 验证扩展加载
curl -s http://localhost:9224/json/list | grep service_worker
# 看到 'type': 'service_worker' + 'url': 'chrome-extension://...' 即成功

# 4. 重启 daemon 让扩展重连
opencli daemon restart && opencli doctor
```

扩展 daemon 监听 `127.0.0.1:19825`。远程连接需 SSH 隧道：
```bash
ssh -L 19825:localhost:19825 root@<服务器IP>
```

### 3d. opencli browser 用法

```bash
opencli doctor                              # 检查连接状态
opencli browser <session> open <URL>         # 打开页面
opencli browser <session> state              # 查看页面元素索引
opencli browser <session> screenshot [path]  # 截图
opencli browser <session> click N            # 点击元素 [N]
opencli browser <session> fill N 'text'      # 填写表单
opencli browser <session> extract            # 提取页面内容为 Markdown
opencli browser <session> console            # 查看控制台日志
opencli browser <session> close              # 关闭会话标签页
```

⚠️ 如果扩展未连接，`opencli browser` 命令直接报错，退回到 Playwright 方案（`browser_navigate` + `browser_console` + `browser_vision`）。

### 3e. opencli douyin adapter 不支持抖店

`opencli douyin` adapter 面向 `creator.douyin.com`（创作者平台），**不支持** `fxg.jinritemai.com`（抖店商家后台）。如需通过 opencli 操作抖店，只能用 `opencli browser fxg <command>` 通用浏览器模式。

### 3f. 二维码时效性
⚠️ 抖店登录二维码有效期约 **2-5 分钟**。远程扫码场景下：
- 生成二维码后立即截图发给用户，同时记录准确时间（`date '+%H:%M:%S'`）
- 用户看到截图时可能已过期，需要时立刻刷新（`browser_navigate` 重新加载页面 → `browser_console` 点击 `.login-switcher--cell`）
- 页面偶尔会加载成空白（白屏），此时需要重新 `browser_navigate`

### 4. 登录成功后跳转
登录成功后，navigate 到订单管理页面：
```
https://fxg.jinritemai.com/ffa/morder/order/list
```

### 5. 订单查询 API（补充）

抖店后台前端 API（无需开放平台凭证，用登录 Cookie 即可）：
- `GET /api/order/orderDetail?order_id=XXX` → 返回 JSON，但手机号/地址脱敏（`1**********`）
- 脱敏字段无法通过此 API 获取明文，需开放平台 `order/getTradeCipher`

抖店开放平台 API（`openapi-fxg.jinritemai.com`）可用于批量订单查询和敏感信息解密，但需要：
- `app_key`、`app_secret`、`access_token`
- 解密接口 `order/getTradeCipher` 有日额度限制（新应用通常几百条/天，需申请提额）
