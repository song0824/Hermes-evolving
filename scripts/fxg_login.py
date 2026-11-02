#!/usr/bin/env python3
"""抖店登录 - 使用独立 Context + Storage State 持久化 Cookie"""
import json, os, time, sys
from pathlib import Path

STORAGE_PATH = Path.home() / ".hermes" / "cache" / "fxg_storage_state.json"

def load_context():
    """启动带 storage state 的 Playwright 浏览器"""
    from playwright.sync_api import sync_playwright
    
    pw = sync_playwright().start()
    
    context_options = {
        "viewport": {"width": 1920, "height": 1080},
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "locale": "zh-CN",
        "timezone_id": "Asia/Shanghai",
    }
    
    # 加载持久化 storage state
    if STORAGE_PATH.exists():
        context_options["storage_state"] = str(STORAGE_PATH)
        print(f"[+] 加载已有 storage state")
    else:
        print("[+] 无已有 storage state，启动新会话")
    
    browser = pw.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--no-sandbox",
        ]
    )
    
    context = browser.new_context(**context_options)
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        window.chrome = {runtime: {}};
    """)
    
    page = context.new_page()
    return pw, browser, context, page

def save_storage(context):
    """保存 storage state"""
    state = context.storage_state()
    STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STORAGE_PATH, "w") as f:
        json.dump(state, f, indent=2)
    print(f"[+] Storage state 已保存 ({len(state.get('cookies', []))} cookies)")

def main():
    pw, browser, context, page = load_context()
    
    try:
        # 导航到登录页
        print(f"[*] 导航到登录页...")
        page.goto("https://fxg.jinritemai.com/login/common?channel=zhaoshang", wait_until="domcontentloaded", timeout=30000)
        print(f"[+] 页面标题: {page.title()}")
        
        # 等待页面加载
        time.sleep(2)
        
        # 查找并点击扫码登录切换按钮
        print("[*] 查找扫码登录切换按钮...")
        
        # 尝试多种选择器
        selectors = [
            '.login-switcher--cell',
            '.daren-login-container',
            '[class*="qrcode"]',
            '[class*="qr-code"]',
            '[class*="scan"]',
            'svg[viewBox]',
        ]
        
        switched = False
        for sel in selectors:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    print(f"[*] 找到元素: {sel}")
                    el.click()
                    time.sleep(2)
                    # 检查页面是否变化
                    if "扫码登录" in page.content() or "qrcode" in page.content().lower():
                        switched = True
                        print(f"[+] 已切换到扫码模式")
                        break
            except Exception as e:
                pass
        
        if not switched:
            # 尝试直接通过 JS 查找可点击的切换按钮
            result = page.evaluate("""
                () => {
                    // 查找登录框右上角的切换按钮
                    const loginPage = document.querySelector('.index_loginPage__K_bGK');
                    if (!loginPage) return 'no login page';
                    
                    // 查找所有带 onclick 或 cursor:pointer 的元素
                    const allEls = loginPage.querySelectorAll('*');
                    for (const el of allEls) {
                        const style = window.getComputedStyle(el);
                        if (style.cursor === 'pointer' && el.children.length <= 3 && el.offsetWidth > 10 && el.offsetWidth < 100) {
                            // 这是一个小的可点击元素，可能是切换按钮
                            const text = el.textContent?.trim();
                            if (!text || text.length < 5) {
                                el.click();
                                return `clicked: ${el.className.substring(0, 50)}`;
                            }
                        }
                    }
                    return 'no button found';
                }
            """)
            print(f"[*] JS 切换结果: {result}")
            time.sleep(2)
        
        # 截图
        qr_path = "/tmp/fxg_qr.png"
        page.screenshot(path=qr_path, full_page=False)
        print(f"[+] 二维码截图: {qr_path}")
        
        # 保存 storage
        save_storage(context)
        
        # 打印 cookie 信息
        cookies = context.cookies()
        print(f"\n[+] 当前 Cookie 数量: {len(cookies)}")
        for c in cookies:
            print(f"    {c['name'][:40]} = {c['value'][:30]}... (domain: {c['domain']})")
        
    except Exception as e:
        print(f"[-] 错误: {e}")
        import traceback
        traceback.print_exc()
        save_storage(context)
    finally:
        browser.close()
        pw.stop()

if __name__ == "__main__":
    main()
