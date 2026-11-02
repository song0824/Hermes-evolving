#!/usr/bin/env python3
"""抖店 - 保持浏览器运行，同一实例内导航"""
import json, time, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

STORAGE_PATH = Path.home() / ".hermes" / "cache" / "fxg_storage_state.json"

pw = sync_playwright().start()

context_opts = {
    "viewport": {"width": 1920, "height": 1080},
    "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "locale": "zh-CN",
    "timezone_id": "Asia/Shanghai",
}

if STORAGE_PATH.exists():
    context_opts["storage_state"] = str(STORAGE_PATH)

browser = pw.chromium.launch(
    headless=True,
    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
)
context = browser.new_context(**context_opts)
context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
page = context.new_page()

# 先导航到登录页获取二维码
print("[*] 导航到登录页...")
page.goto("https://fxg.jinritemai.com/login/common?channel=zhaoshang", wait_until="domcontentloaded", timeout=30000)
time.sleep(2)

el = page.query_selector(".login-switcher--cell")
if el:
    el.click()
    time.sleep(2)

page.screenshot(path="/tmp/fxg_qr.png", full_page=False)
print("[+] 二维码已生成: /tmp/fxg_qr.png")

# 保存初始状态
state = context.storage_state()
with open(STORAGE_PATH, "w") as f:
    json.dump(state, f, indent=2)

print("[*] 等待扫码登录 (最多120秒)...")
logged_in = False
for i in range(60):
    time.sleep(2)
    current_url = page.url
    
    if "login" not in current_url.lower():
        print(f"\n[+] 检测到登录成功! URL: {current_url}")
        logged_in = True
        break
    elif i % 10 == 0:
        print(f"[*] 等待中... ({i*2}秒)")

if not logged_in:
    print("\n[-] 超时未检测到登录成功")

# 扫码成功后导航到订单列表
if logged_in:
    print("[*] 导航到订单列表页...")
    page.goto("https://fxg.jinritemai.com/ffa/morder/order/list", wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)
    page.screenshot(path="/tmp/fxg_order_list.png", full_page=False)
    print(f"[+] 订单页 URL: {page.url}")
    print(f"[+] 订单页标题: {page.title()}")

# 最终保存
state = context.storage_state()
with open(STORAGE_PATH, "w") as f:
    json.dump(state, f, indent=2)

cookies = context.cookies()
print(f"\n[+] 最终 Cookie: {len(cookies)}")
for c in cookies:
    name = c["name"]
    is_login = "session" in name.lower() or "sid" in name.lower() or "token" in name.lower()
    if is_login:
        print(f"    {name}: {c['value'][:30]}...")

page.screenshot(path="/tmp/fxg_final.png", full_page=False)

browser.close()
pw.stop()
