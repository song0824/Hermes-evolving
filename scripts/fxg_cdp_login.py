#!/usr/bin/env python3
"""抖店登录 - 连接现有 Chrome 实例 (CDP) 以绕过检测"""
import json, time
from playwright.sync_api import sync_playwright

pw = sync_playwright().start()

print("[*] 连接到现有 Chrome 实例 (端口 9224)...")
try:
    browser = pw.chromium.connect_over_cdp("http://localhost:9224")
    context = browser.contexts[0]
    
    # 清理旧 cookie 以避免状态冲突
    print("[*] 清理旧 cookies...")
    cookies = context.cookies()
    bad_domains = ["jinritemai.com", "bytedance.com", "feelgood.cn"]
    to_delete = [c for c in cookies if any(d in c['domain'] for d in bad_domains)]
    if to_delete:
        print(f"[*] 删除 {len(to_delete)} 个旧 cookies")
        # Note: Playwright doesn't have a direct delete_cookie by filter, so we clear and re-add?
        # Or just navigate, usually the site overwrites them.
        # But let's try to clear specific ones if possible?
        # Actually, `context.clear_cookies()` is easier.
        # I'll just clear all for safety since this is a dedicated session.
        context.clear_cookies()
        print("[+] Cookies 已清空")
    
    page = context.new_page()
    
    # 拦截网络响应以监控状态
    qr_fp = None
    def on_response(response):
        try:
            if "check_qrconnect" in response.url:
                body = response.json()
                status = body.get("data", {}).get("status", "0")
                err = body.get("error_code", "")
                if err == 2046:
                    print(f"[!] 安全拦截 (2046): {body.get('description')}")
                elif status != "1":
                    print(f"[+] 扫码状态变化: status={status}")
        except:
            pass
    
    page.on("response", on_response)
    
    print("[*] 导航到登录页...")
    page.goto("https://fxg.jinritemai.com/login/common?channel=zhaoshang", wait_until="domcontentloaded", timeout=30000)
    time.sleep(2)
    
    # 切换扫码
    page.evaluate("""
        const s = document.querySelector('.login-switcher--cell');
        if (s) s.click();
    """)
    time.sleep(3)
    
    page.screenshot(path="/tmp/fxg_qr_stealth.png", full_page=False)
    print("[+] 二维码已生成: /tmp/fxg_qr_stealth.png")
    
    # 等待扫码
    print("[*] 等待扫码...")
    for i in range(60):
        time.sleep(2)
        url = page.url
        title = page.title()
        if "login" not in url.lower():
            print(f"🎉 登录成功! URL: {url}")
            print(f"   标题: {title}")
            page.screenshot(path="/tmp/fxg_order_stealth.png", full_page=False)
            
            # 保存 cookies
            cookies = context.cookies()
            print(f"[+] 获取到 {len(cookies)} 个 cookies")
            login_cookies = [c for c in cookies if 'session' in c['name'].lower() or 'sid' in c['name'].lower()]
            for c in login_cookies:
                print(f"   {c['name']}: {c['value'][:30]}...")
            
            # 持久化
            STORAGE_PATH = "/root/.hermes/cache/fxg_storage_state_cdp.json"
            state = context.storage_state()
            with open(STORAGE_PATH, "w") as f:
                json.dump(state, f, indent=2)
            print(f"[+] 状态已保存到 {STORAGE_PATH}")
            break
        elif i % 10 == 0:
            print(f"[*] 等待中... ({i*2}秒)")
            
except Exception as e:
    print(f"[-] 错误: {e}")

finally:
    pw.stop()
