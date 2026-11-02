#!/usr/bin/env python3
"""
Connect to real Chrome (CDP) to bypass detection.
Generate QR code for DouDian App.
"""
import json, time, sys
from playwright.sync_api import sync_playwright

print("[*] Connecting to real Chrome via CDP...", flush=True)
pw = sync_playwright().start()

try:
    browser = pw.chromium.connect_over_cdp("http://localhost:9224")
    context = browser.contexts[0]
    
    # Create a new page
    page = context.new_page()
    
    # Monitor QR generation
    qr_info = {}
    def on_response(response):
        if "get_qrcode" in response.url:
            try:
                body = response.json()
                data = body.get("data", {})
                qr_info["copywriting"] = data.get("copywriting", "")
                qr_info["app_name"] = data.get("app_name", "")
                print(f"[QR] App: {qr_info['app_name']}", flush=True)
                print(f"[QR] Copywriting: {qr_info['copywriting'][:100]}...", flush=True)
            except Exception as e:
                print(f"[QR] Error parsing: {e}", flush=True)
    
    page.on("response", on_response)

    print("[*] Navigating to login page...", flush=True)
    # Use standard login URL to hopefully trigger DouDian App QR code
    page.goto("https://fxg.jinritemai.com/login/common", wait_until="domcontentloaded", timeout=30000)
    
    # Wait a bit for scripts to run
    time.sleep(3)
    
    # Try to find and click QR switch if not already there
    # We look for the QR icon in the login box
    qr_icon = page.query_selector('[class*="qrcode"], [class*="qr-icon"]')
    # If not found, try clicking the generic switch
    if not qr_icon:
        # Try clicking the 'login-switcher--cell' again
        page.evaluate("""
            const s = document.querySelector('.login-switcher--cell');
            if (s) s.click();
        """)
        time.sleep(2)
        
        # Or try clicking the small QR icon at top right of login box
        page.evaluate("""
            const icons = document.querySelectorAll('.account-center-header .question-container, .index_loginPage__K_bGK i, .index_loginPage__K_bGK svg');
            for(let el of icons) {
                if(el.offsetParent !== null) { // visible
                     el.click();
                     break;
                }
            }
        """)
        time.sleep(2)

    page.screenshot(path="/tmp/fxg_qr_cdp.png", full_page=False)
    print("[+] Screenshot saved to /tmp/fxg_qr_cdp.png", flush=True)
    
    if qr_info.get("copywriting"):
        print(f"[INFO] QR Code Text: {qr_info['copywriting'][:200]}", flush=True)
        if "抖店" in qr_info["copywriting"] or "DouDian" in qr_info.get("app_name", ""):
            print("[SUCCESS] QR Code seems to be for DouDian App!", flush=True)
        else:
            print("[WARNING] QR Code might for Douyin App or other!", flush=True)
            
    # Keep running to detect login
    print("[*] Waiting for scan...", flush=True)
    for i in range(60):
        time.sleep(2)
        url = page.url
        if "login" not in url.lower() and "common" not in url.lower():
            print(f"🎉 Login Detected! URL: {url}", flush=True)
            page.screenshot(path="/tmp/fxg_logged_in_cdp.png", full_page=False)
            
            # Save state
            state = context.storage_state()
            with open("/root/.hermes/cache/fxg_storage_state.json", "w") as f:
                json.dump(state, f, indent=2)
            print("[+] State saved.", flush=True)
            
            # Go to order list
            page.goto("https://fxg.jinritemai.com/ffa/morder/order/list", wait_until="domcontentloaded", timeout=30000)
            time.sleep(5)
            page.screenshot(path="/tmp/fxg_order_cdp.png", full_page=False)
            print(f"[+] Order Page: {page.url}", flush=True)
            print(f"[+] Order Page Title: {page.title()}", flush=True)
            break
        elif i % 10 == 0:
            print(f"[*] Waiting... ({i*2}s)", flush=True)

except Exception as e:
    print(f"[-] Error: {e}", flush=True)
finally:
    pw.stop()
