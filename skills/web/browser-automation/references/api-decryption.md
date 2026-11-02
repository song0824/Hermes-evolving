# 抖店开放平台 API 解密与收货人明文获取

## 开放平台 API 解密流程

### 端点与接口
```
Base: op.jinritemai.com
接口链: order.getOrderList → order.getOrderDetail → order.getTradeCipher
cipher_type: 1=手机号, 2=地址, 3=姓名
```

### 配额限制
| 账号类型 | 解密配额/天 |
|----------|------------|
| 子账号 | ~290 次 |
| 主账号 | 1万-20万次 (需申请) |

## 获取明文收货信息的三种方案

| 方案 | 适用场景 | 限制 |
|------|----------|------|
| **抖店开放平台 API** | 有 app_key/app_secret | `order/getTradeCipher` 解密，子账号配额 ~290次/天，主账号 1万-20万次/天 |
| **后台导出申请明文权限** | 大批量（5000+单） | 抖店后台 → 权限管理 → 申请明文导出权限，审核 1-3 工作日 |
| **第三方 ERP/打单软件** | 已有系统 | 风火递、聚水潭等通常已有明文权限 |

## Cookie 格式 (完整)
```
sid_tt=<value>
session_id=<value>
sessionid_ss=<value>
sid_guard=<value>%7C<timestamp>%7C<duration>%7C<date>
PHPSESSID=<value>
PHPSESSID_SS=<value>
ecom_us_lt=<value>
csrf_session_id=<value>
```
有效期约 60 天（sid_guard 中 encoded），但可能提前失效。

## 订单详情 API 返回结构
```json
{
  "errno": 0,
  "data": {
    "order_id": "...",
    "order_base": { "labels": [...] },
    "receiver": {
      "post_receiver": "洛*",
      "post_tel": "1**********",
      "post_addr": {
        "province": {"name": "广西壮族自治区"},
        "city": {"name": "北海市"},
        "town": {"name": "海城区"},
        "street": {"name": "驿马街道"},
        "detail": "***********"
      },
      "can_view": 1
    },
    "product": { "sku": [...] },
    "delivery": { "labels": [...] }
  }
}
```

## 后台明文权限申请路径
1. 抖店后台 → 店铺 → 店铺管理 → 权限管理
2. 找到「订单导出明文权限」或「收货人信息导出权限」
3. 提交申请（说明用途、提供资质）
4. 等待审核（1-3 工作日）

## 常见问题
- Cookie 失效时返回 `{"code":"10008","msg":"登录信息已失效"}`
- 订单详情 API 触发滑块验证码（`verify_type: slide`）时需 UI 交互
