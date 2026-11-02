# Douyin Store UI Scraping via opencli Browser

## Session Profile Setup
```bash
opencli browser <session> open "https://fxg.jinritemai.com/login/common?channel=zhaoshang"
opencli browser <session> click 1    # Switch to QR scan mode
opencli browser <session> screenshot /tmp/qr.png
```

## Login Flow
1. Open `https://fxg.jinritemai.com/login/common?channel=zhaoshang`
2. Click element [1] to switch to QR scan mode
3. Screenshot and provide QR to user for **抖店 APP** scan
4. QR codes expire in ~2-5 minutes — generate fresh ones on demand

## Order Extraction via UI
After login, navigate to order list:
```bash
opencli browser <session> open "https://fxg.jinritemai.com/ffa/morder/order/list"
opencli browser <session> state   # Get interactive elements
```

## Critical Limitation: Decryption Requires Slider CAPTCHA
- The Douyin Store UI requires a **slider CAPTCHA** to reveal plaintext phone/address
- Each order detail view triggers this captcha — making bulk UI scraping impractical
- API (`/api/order/orderDetail`) returns masked data (`1**********`, `***********`)
- Only the Open Platform API (`order/getTradeCipher`) bypasses the captcha for bulk operations

## Recommended Approach
For bulk order extraction with shipping contact info:
1. **Preferred**: Use Douyin Open Platform API with app_key/app_secret
2. **Alternative**: Backend export with 明文导出权限 applied
3. **Last resort**: UI scraping one-by-one (slider captcha per order)

## Cookie Notes
- `sid_tt`, `session_id`, `sessionid_ss`, `sid_guard` are HttpOnly — cannot be set via `document.cookie`
- Must inject via CDP protocol or DevTools Application tab
- Expired cookies return: `{"code":"10008","msg":"登录信息已失效"}`
