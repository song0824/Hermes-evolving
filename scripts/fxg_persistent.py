#!/usr/bin/env python3
"""抖店登录 - 高频轮询扫码状态"""
import json, time, sys, signal, base64
from pathlib import Path
from playwright.sync_api import sync_playwright

STORAGE_PATH = Path.home() / ".hermes" / "cache" / "fxg_storage_state.json"
LOG_PATH = Path.home() / ".hermes" / "cache" / "fxg_browser.log"

running = True
def handle_sig(s, f):
    global running
    running = False

signal.signal(signal.SIGTERM, handle_sig)
signal.signal(signal.SIGINT, handle_sig)

def log(msg):
    t = time.strftime("%H:%M:%S")
    print(f"[{t}] {msg}", flush=True)

pw = sync_playwright().start()

context_opts = {
    "viewport": {"width": 1920, "height": 1080},
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "locale": "zh-CN",
    "timezone_id": "Asia/Shanghai",
}

if STORAGE_PATH.exists():
    context_opts["storage_state"] = str(STORAGE_PATH)
    log("加载 storage state")

browser = pw.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled', '--no-sandbox'])
context = browser.new_context(**context_opts)
context.add_init_script("""
    Object.defineProperty(navigator, 'webdriver', {get: () => false});
    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
    window.chrome = {runtime: {}, loadTimes: () => ({}), csi: () => ({})};
""")
page = context.new_page()

# 监听关键网络响应
qr_fp = None
def on_response(response):
    global qr_fp
    try:
        url = response.url
        if "get_qrcode" in url:
            body = response.json()
            qr_fp = body.get("data", {}).get("qrcode", "")[:20]
            log(f"[QR] 获取二维码成功")
        elif "check_qrconnect" in url:
            try:
                body = response.json()
                status = body.get("data", {}).get("status", "0")
                err_code = body.get("error_code", "")
                if status != "1":
                    log(f"[QR] 状态变化! status={status}, error_code={err_code}")
            except:
                pass
        elif "check_login" in url:
            try:
                body = response.json()
                has_login = body.get("has_login", body.get("subject_has_login", False))
                if has_login:
                    log(f"[LOGIN] 检测到登录成功!")
            except:
                pass
    except:
        pass

page.on("response", on_response)

# 导航到登录页
log("导航到登录页...")
page.goto("https://fxg.jinritemai.com/login/common?channel=zhaoshang", wait_until="domcontentloaded", timeout=30000)
time.sleep(2)

# 切换到扫码登录
el = page.query_selector(".login-switcher--cell")
if el:
    el.click()
    time.sleep(3)
    log("已切换到扫码登录模式")

page.screenshot(path="/tmp/fxg_qr.png", full_page=False)
log("二维码已生成: /tmp/fxg_qr.png")

def save():
    state = context.storage_state()
    with open(STORAGE_PATH, "w") as f:
        json.dump(state, f, indent=2)
    return len(state.get("cookies", []))

log(f"初始 cookies: {save()}")

# 高频轮询（每1秒）
log("等待扫码登录 (每1秒轮询)...")
start = time.time()
while running:
    time.sleep(1)
    elapsed = int(time.time() - start)
    url = page.url
    title = page.title()
    
    # 检查是否离开登录页
    if "login" not in url.lower():
        log(f"🎉 检测到页面跳转!")
        log(f"URL: {url}")
        log(f"标题: {title}")
        
        cookies = context.cookies()
        log(f"Cookie 数量: {len(cookies)}")
        for c in cookies:
            name = c["name"].lower()
            if any(k in name for k in ["session", "sid", "token", "login", "user"]):
                log(f"  {c['name']}: {c['value'][:40]}...")
        
        save()
        
        # 截图
        page.screenshot(path="/tmp/fxg_logged_in.png", full_page=False)
        
        # 导航到订单列表
        log("导航到订单列表页...")
        page.goto("https://fxg.jinritemai.com/ffa/morder/order/list", wait_until="domcontentloaded", timeout=30000)
        time.sleep(5)
        log(f"订单页 URL: {page.url}")
        log(f"订单页标题: {page.title()}")
        page.screenshot(path="/tmp/fxg_order.png", full_page=False)
        
        body = page.evaluate("() => document.body.innerText?.substring(0, 500)")
        log(f"页面内容: {body[:300]}")
        
        save()
        break
    elif elapsed % 10 == 0:
        log(f"等待中... {elapsed}秒, title: {title}")

log("浏览器关闭")
browser.close()
pw.stop()
