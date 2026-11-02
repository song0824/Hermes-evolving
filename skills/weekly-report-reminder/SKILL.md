---
name: weekly-report-reminder
description: 每周一 11:00 自动检查技术周会知识库中的最新周报文档，分析谁未填写，并 @ 未填写的人发送到研发运维群。
category: productivity
---

# 技术周会周报催填任务

可执行脚本：`scripts/weekly_report_reminder.py`。cron 打开后应运行该脚本，不要按旧标题格式手写一遍。

```bash
python scripts/weekly_report_reminder.py
```

## ⚠️ 节假日检查（最高优先级）

**执行任何操作前，先检查当天是否为中国法定节假日。**

节假日日期列表见 `references/china-holidays.md`。脚本内已内置同一套日期。节假日输出 `SKIP|...` 后直接终止。

## 与创建脚本的对齐

创建脚本 `scripts/weekly_tech_meeting.py` 现在会：

- 把文档建在知识库父节点 `AAGlw95lZi4sUqk78vzc7mkHnIb` 下
- 标题为 `技术周会 YYYY-MM-DD`（同时兼容旧标题 `YYYY年M月D日`）
- 各人小节是 H3 里的飞书 `mention_user`（通讯录芯片），不是纯文本 `@用户`
- 创建通知发到研发运维群 `oc_611b7861968a34f8c2f538f67410b629`

催填必须认两种标题日期，用 H3 的 `user_id` 做 @，消息发到同一个研发运维群。

## 任务流程

### 1. 获取凭证

从 `~/.hermes/config.yaml` 读取 Feishu App ID 和 Secret，获取 `tenant_access_token`。

### 2. 定位知识库和最新周报文档

知识库 wiki token: `AAGlw95lZi4sUqk78vzc7mkHnIb`

```python
def extract_date_from_title(title):
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", title or "")
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", title or "")
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return "0000-00-00"

items.sort(key=lambda x: extract_date_from_title(x.get("title", "")), reverse=True)
```

脚本只在标题含「技术周会」、日期落在今天及之前 7 天内的文档里选择。这个窗口内如果有多份（机器人重复创建时），比较每份的已填写人数，用写得更多的那份；都没人写时才用较新的一份。7 天以外的旧周报不参与。窗口内一份读不到就跳过，改看其余几份；全部读不到才失败。

### 3. 读取文档并判断谁未填写

- H3 里的 `mention_user.user_id` 只和同一标题行的 `@名字` 配对。行首 `@` 的个数必须等于该标题的芯片数。
- 正文里的 `@`、多出来的 `@` 行、或数量对不上时，脚本失败退出，不发消息。
- 标题同一行 `@名字` 后面的文字算已填写。模板占位行（如「请填写」「（请填写本周工作）」）不算。
- 催填 @ 用配对得到的 `user_id`。

### 4. 发送催填消息到研发运维群

目标群: `oc_611b7861968a34f8c2f538f67410b629`

```python
at_tags = "".join(f'<at user_id="{uid}">{name}</at>' for uid, name in unfilled)
message_text = (
    f"{at_tags}\n\n技术周会周报催填\n\n"
    f"还有 {len(unfilled)} 位同学未填写周报，请尽快补充。\n\n"
    f"文档链接：{doc_url}\n\n"
    f"已填写（{len(filled)}人）：{filled_names}"
)
```

`msg_type` 为 `text`。无人未填则不发消息。

### 5. 输出结果

cron 输出打印文档标题、已填写、未填写、消息是否发出。

## 注意事项

- 7 天窗口内有一份读不到时跳过该份。全部读不到才报错退出，给文档补上应用协作者后重跑。不要改去催 7 天以前的周报。
- 标题日期同时认 `YYYY-MM-DD` 和 `YYYY年M月D日`，并且标题里要有「技术周会」。
- 目标群：`oc_611b7861968a34f8c2f538f67410b629`（研发运维群）
- 知识库 wiki token：`AAGlw95lZi4sUqk78vzc7mkHnIb`
- App ID: `cli_a97b1e4633f99cb0`
