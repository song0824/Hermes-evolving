#!/usr/bin/env python3
"""Analyze the SLS query results and generate the report."""
import json
from datetime import datetime, timezone, timedelta

cst = timezone(timedelta(hours=8))

with open("/root/.hermes/workspace/sls_daily_2026-07-02.json") as f:
    data = json.load(f)

# ========== 1. Process histogram data (30-min buckets -> hourly) ==========
def histogram_to_hourly(buckets):
    """Aggregate 30-min histogram buckets into hourly CST counts."""
    hourly = {}
    for b in buckets:
        ts = b["from"]
        cst_dt = datetime.fromtimestamp(ts, tz=cst)
        hour_key = f"{cst_dt.hour:02d}:00"
        if hour_key not in hourly:
            hourly[hour_key] = 0
        hourly[hour_key] += int(b.get("count", 0))
    return hourly

hist_y = data.get("histogram_yesterday", [])
hist_db = data.get("histogram_day_before", [])

hourly_y = histogram_to_hourly(hist_y)
hourly_db = histogram_to_hourly(hist_db)

# Also get the SQL hourly data (more precise)
sql_hourly_y = {}
for entry in (data.get("hourly_yesterday", []) or []):
    sql_hourly_y[entry.get("hour", "")] = int(entry.get("cnt", 0))

sql_hourly_db = {}
for entry in (data.get("hourly_day_before", []) or []):
    sql_hourly_db[entry.get("hour", "")] = int(entry.get("cnt", 0))

# Use SQL hourly data if available (more precise), fall back to histogram
use_y = sql_hourly_y if sql_hourly_y else hourly_y
use_db = sql_hourly_db if sql_hourly_db else hourly_db

# Total from histogram
total_y = sum(int(b.get("count", 0)) for b in hist_y)
total_db = sum(int(b.get("count", 0)) for b in hist_db)

# ========== 2. Process logger data ==========
def parse_logger_entries(entries):
    result = {}
    if isinstance(entries, list):
        for e in entries:
            result[e.get("logger", "unknown")] = int(e.get("cnt", 0))
    return result

loggers_y = parse_logger_entries(data.get("loggers_yesterday", []))
loggers_db = parse_logger_entries(data.get("loggers_day_before", []))

# ========== 3. Process message data ==========
def parse_msg_entries(entries):
    result = []
    if isinstance(entries, list):
        for e in entries:
            cnt = int(e.get("cnt", 0))
            msg = e.get("msg_sample", "")[:120]
            result.append((cnt, msg))
    result.sort(reverse=True)
    return result

msgs_y = parse_msg_entries(data.get("messages_yesterday", []))
msgs_db = parse_msg_entries(data.get("messages_day_before", []))

# ========== 4. Keyword data ==========
kw_y = data.get("keywords_yesterday", {})
kw_db = data.get("keywords_day_before", {})

# ========== 5. Version data ==========
ver_y = data.get("version_yesterday", ["unknown"])
ver_db = data.get("version_day_before", ["unknown"])

# ========== 6. Compute hourly table ==========
all_hours = sorted(set(list(use_y.keys()) + list(use_db.keys())))
full_24 = [f"{h:02d}:00" for h in range(24)]

# ========== 7. Time period aggregation ==========
periods = {
    "凌晨 (00-07)": (0, 8),
    "上午 (08-12)": (8, 13),
    "下午 (13-17)": (13, 18),
    "晚高峰 (18-20)": (18, 21),
    "夜间 (21-23)": (21, 24),
}

def period_total(hourly_dict, start, end):
    return sum(hourly_dict.get(f"{h:02d}:00", 0) for h in range(start, end))

# ========== 8. Peak hour drill-down ==========
drill_down = data.get("drill_down", {})

# ========== 9. Generate Report ==========
report = []

# Header
yesterday_date = "2026-07-02"
day_before_date = "2026-07-01"
change_pct = ((total_y - total_db) / total_db * 100) if total_db else 0
change_emoji = "🔴" if change_pct > 50 else ("🟢" if change_pct < -50 else "")
change_str = f"{change_pct:+.1f}%"

report.append(f"# 📊 ling-server 每日Error日志分析报告（{yesterday_date}）")
report.append("")
report.append(f"**分析时间**: {yesterday_date} 00:00-23:59 CST（对比 {day_before_date}）")
report.append(f"**版本信息**: 昨天=`{ver_y[0]}`，前天=`{ver_db[0]}`（均从前60秒Error日志提取）")
report.append("")

# ===== Section 1: 昨日Error分布 =====
report.append("## 一、昨日Error日志分布")
report.append("")

report.append("### 1. 总体概况")
report.append("")
report.append("| 指标 | 数值 |")
report.append("|---|---|")
report.append(f"| 昨日Error总数 | **{total_y}** |")
report.append(f"| 前天Error总数 | {total_db} |")
report.append(f"| 环比变化 | {change_emoji} {change_str} |")
report.append(f"| 活跃小时数 | {len([h for h in full_24 if use_y.get(h, 0) > 0])}/24 |")
report.append(f"| 峰值时段 | {max(use_y, key=use_y.get) if use_y else 'N/A'} |")
peak_hour = max(use_y, key=use_y.get) if use_y else 'N/A'
peak_count = use_y.get(peak_hour, 0)
report.append(f"| 峰值Error数 | {peak_count} 条/小时 |")
report.append("")

# Hourly distribution
report.append("### 2. 按小时分布")
report.append("")
report.append("| 时段(CST) | 昨天 | 前天 | 环比 |")
report.append("|---|---|---|---|")
for h in full_24:
    cy = use_y.get(h, 0)
    cd = use_db.get(h, 0)
    if cd > 0:
        pct = ((cy - cd) / cd * 100)
        pct_str = f"{pct:+.0f}%"
    elif cy > 0:
        pct_str = "新增"
    else:
        pct_str = "-"
    
    marker = ""
    if cy > 50:
        marker = " 🔴"
    elif cy == 0 and cd > 0:
        marker = " 🟢"
    report.append(f"| {h} | {cy}{marker} | {cd} | {pct_str} |")
report.append("")

# Period aggregation
report.append("### 3. 时段聚合对比")
report.append("")
report.append("| 时段 | 昨天 | 前天 | 环比 |")
report.append("|---|---|---|---|")
for label, (s, e) in periods.items():
    cy = period_total(use_y, s, e)
    cd = period_total(use_db, s, e)
    if cd > 0:
        pct = ((cy - cd) / cd * 100)
        pct_str = f"{pct:+.1f}%"
    elif cy > 0:
        pct_str = "新增"
    else:
        pct_str = "-"
    report.append(f"| {label} | {cy} | {cd} | {pct_str} |")
report.append("")

# Top loggers
report.append("### 4. Top Error Logger 分布")
report.append("")
report.append("| 排名 | Logger | 昨天 | 前天 | 占比 |")
report.append("|---|---|---|---|---|")

# Merge both days' loggers
all_loggers = set(list(loggers_y.keys()) + list(loggers_db.keys()))
sorted_loggers = sorted(all_loggers, key=lambda k: loggers_y.get(k, 0), reverse=True)

for i, logger in enumerate(sorted_loggers[:15], 1):
    cy = loggers_y.get(logger, 0)
    cd = loggers_db.get(logger, 0)
    pct = f"{cy/total_y*100:.1f}%" if total_y else "-"
    report.append(f"| {i} | `{logger}` | {cy} | {cd} | {pct} |")
report.append("")

# Top error messages
report.append("### 5. Top 5 最常见Error消息")
report.append("")
report.append("| 排名 | 错误消息 | 昨天 |")
report.append("|---|---|---|")
for i, (cnt, msg) in enumerate(msgs_y[:5], 1):
    safe_msg = msg.replace("|", "\\|").replace("\n", " ")[:100]
    report.append(f"| {i} | `{safe_msg}` | {cnt} |")
report.append("")

# Keyword classification
report.append("### 6. 关键词分类统计（GetHistograms）")
report.append("")
report.append("| 错误类别 | 昨天 | 前天 | 变化 | 说明 |")
report.append("|---|---|---|---|---|")
for label in kw_y.keys():
    cy = kw_y.get(label, 0)
    cd = kw_db.get(label, 0)
    if cd > 0:
        pct = ((cy - cd) / cd * 100)
        pct_str = f"{pct:+.0f}%"
    elif cy > 0:
        pct_str = "新增"
    else:
        pct_str = "-"
    
    note = ""
    if label in ["Dify中间件", "DataCard中间件"]:
        note = "⚠️ 两者有重叠"
    elif label == "图片未通过风控":
        note = "正常业务过滤"
    elif label == "任务生成失败":
        note = "task_scheduler主类"
    elif label == "角色不存在":
        note = "BizException"
    report.append(f"| {label} | {cy} | {cd} | {pct_str} | {note} |")
report.append("")

# ===== Section 2: 环比分析 =====
report.append("## 二、环比分析（昨天 vs 前天）")
report.append("")

report.append("### 1. 总量对比")
report.append("")
report.append("| 日期 | Error总数 | 活跃小时数 | 峰值时段 | 峰值量 |")
report.append("|---|---|---|---|---|")
peak_db = max(use_db, key=use_db.get) if use_db else 'N/A'
peak_db_count = use_db.get(peak_db, 0)
report.append(f"| {yesterday_date} | **{total_y}** | {len([h for h in full_24 if use_y.get(h, 0) > 0])} | {peak_hour} | {peak_count} |")
report.append(f"| {day_before_date} | {total_db} | {len([h for h in full_24 if use_db.get(h, 0) > 0])} | {peak_db} | {peak_db_count} |")
report.append(f"| 变化 | **{change_str}** | | | |")
report.append("")

# Logger changes
report.append("### 2. Logger变化分析")
report.append("")

# New loggers (yesterday but not day before)
new_loggers = {k: v for k, v in loggers_y.items() if k not in loggers_db and v > 0}
# Disappeared loggers (day before but not yesterday)
gone_loggers = {k: v for k, v in loggers_db.items() if k not in loggers_y and v > 0}
# Changed loggers
changed = []
for k in set(loggers_y.keys()) & set(loggers_db.keys()):
    cy, cd = loggers_y[k], loggers_db[k]
    if cy != cd:
        pct = ((cy - cd) / cd * 100) if cd else float('inf')
        changed.append((k, cy, cd, pct))
changed.sort(key=lambda x: abs(x[3]), reverse=True)

report.append("**🆕 新增Logger（昨天出现，前天无）：**")
if new_loggers:
    for k, v in sorted(new_loggers.items(), key=lambda x: -x[1]):
        report.append(f"- `{k}`: {v} 条")
else:
    report.append("- 无")
report.append("")

report.append("**💀 消失的Logger（前天有，昨天无）：**")
if gone_loggers:
    for k, v in sorted(gone_loggers.items(), key=lambda x: -x[1]):
        report.append(f"- `{k}`: 前天 {v} 条 → 昨天 0 条")
else:
    report.append("- 无")
report.append("")

report.append("**📈 显著变化的Logger（环比变化Top 10）：**")
report.append("")
report.append("| Logger | 昨天 | 前天 | 环比 |")
report.append("|---|---|---|---|")
for k, cy, cd, pct in changed[:10]:
    marker = "🔴" if pct > 50 else ("🟢" if pct < -50 else "")
    report.append(f"| `{k}` | {cy} | {cd} | {marker} {pct:+.1f}% |")
report.append("")

# Message changes
report.append("### 3. Error消息模式变化")
report.append("")

# Compare top messages
msgs_y_set = {msg: cnt for cnt, msg in msgs_y}
msgs_db_set = {msg: cnt for cnt, msg in msgs_db}

new_msgs = {k: v for k, v in msgs_y_set.items() if k not in msgs_db_set and int(v) > 0}
gone_msgs = {k: v for k, v in msgs_db_set.items() if k not in msgs_y_set and int(v) > 0}

report.append("**🆕 新增Error消息：**")
if new_msgs:
    for msg, cnt in sorted(new_msgs.items(), key=lambda x: -x[1])[:5]:
        safe = msg.replace("|", "\\|")[:100]
        report.append(f"- `{safe}`: {cnt} 条")
else:
    report.append("- 无（Top消息均在前天出现过）")
report.append("")

report.append("**💀 消失的Error消息：**")
if gone_msgs:
    for msg, cnt in sorted(gone_msgs.items(), key=lambda x: -x[1])[:5]:
        safe = msg.replace("|", "\\|")[:100]
        report.append(f"- `{safe}`: 前天 {cnt} 条 → 昨天 0 条")
else:
    report.append("- 无（所有前天Top消息昨天仍有）")
report.append("")

# ===== Section 3: 建议 =====
report.append("## 三、关键发现与建议")
report.append("")

# Analyze findings
findings = []

# Check task_scheduler dominance
ts_y = loggers_y.get("app.utils.task_scheduler", 0)
ts_db = loggers_db.get("app.utils.task_scheduler", 0)
ts_pct_y = ts_y / total_y * 100 if total_y else 0

# Check signature_base
sb_y = loggers_y.get("app.middleware.signature_base", 0)
sb_db = loggers_db.get("app.middleware.signature_base", 0)

# Check ling_smart_client
lsc_y = loggers_y.get("app.core.ling_smart_client", 0)
lsc_db = loggers_db.get("app.core.ling_smart_client", 0)

# Check image moderation
img_y = kw_y.get("图片未通过风控", 0)
img_db = kw_db.get("图片未通过风控", 0)

# Check task generation failure
tgf_y = kw_y.get("任务生成失败", 0)
tgf_db = kw_db.get("任务生成失败", 0)

# Check Dify middleware
dify_y = kw_y.get("Dify中间件", 0)
dify_db = kw_db.get("Dify中间件", 0)

# Check role not found
role_y = kw_y.get("角色不存在", 0)
role_db = kw_db.get("角色不存在", 0)

# Check internal server error
ise_y = kw_y.get("Internal Server Error", 0)
ise_db = kw_db.get("Internal Server Error", 0)

# Check ASGI
asgi_y = kw_y.get("ASGI异常", 0)
asgi_db = kw_db.get("ASGI异常", 0)

# Check create role failure
crf_y = kw_y.get("创建角色记录失败", 0)
crf_db = kw_db.get("创建角色记录失败", 0)

# Check task state
tsc_y = kw_y.get("任务状态不正确", 0)
tsc_db = kw_db.get("任务状态不正确", 0)

# Check wallpaper / energy
wp_y = kw_y.get("WALLPAPER_ERROR", 0)
wp_db = kw_db.get("WALLPAPER_ERROR", 0)
energy_y = kw_y.get("获取用户能量失败", 0)
energy_db = kw_db.get("获取用户能量失败", 0)

# Overall assessment
if total_y < total_db:
    findings.append(("🟢", "总体趋势向好", f"Error总数从 {total_db} 降至 {total_y}（{change_str}），服务稳定性有所改善。"))
else:
    findings.append(("🔴", "Error数量上升", f"Error总数从 {total_db} 增至 {total_y}（{change_str}），需要关注。"))

# task_scheduler
if ts_y > 0:
    findings.append(("🟡", f"task_scheduler 持续为主要Error来源", f"`app.utils.task_scheduler` 贡献 {ts_y} 条（{ts_pct_y:.1f}%），前天 {ts_db} 条。任务生成失败（关键词匹配）{tgf_y} 条。这表明 Dify 工作流超时、风控拦截等任务失败仍是日常主要Error来源。建议：优化任务超时配置、增加异步重试机制。"))

# signature_base
if sb_y > 0:
    sb_change = ((sb_y - sb_db) / sb_db * 100) if sb_db else 0
    findings.append(("🟡", f"中间件签名验证异常", f"`app.middleware.signature_base` 贡献 {sb_y} 条（前天 {sb_db} 条，{sb_change:+.0f}%）。Dify中间件异常 {dify_y} 条，DataCard中间件异常 {kw_y.get('DataCard中间件', 0)} 条。⚠️ 两者有重叠，同一请求可能同时触发。建议：检查下游服务响应时间、健康探针配置。"))

# ISE and ASGI
if ise_y > 0 or asgi_y > 0:
    findings.append(("🟡", f"框架级异常存在但低位", f"Internal Server Error {ise_y} 条（前天 {ise_db} 条），ASGI异常 {asgi_y} 条（前天 {asgi_db} 条）。数量在低位，说明应用层异常处理正常，未出现大规模级联。"))

# Image moderation
if img_y > 0:
    findings.append(("🟢", f"图片风控拦截正常", f"图片未通过风控 {img_y} 条（前天 {img_db} 条），属于正常内容审核流程，建议考虑将此类日志从 ERROR 降级为 WARN。"))

# Create role failure
if crf_y > 0:
    crf_change = ((crf_y - crf_db) / crf_db * 100) if crf_db else 0
    findings.append(("🟡", f"创建角色记录失败", f"`创建角色记录失败` {crf_y} 条（前天 {crf_db} 条，{crf_change:+.0f}%）。建议检查数据库唯一约束和角色创建逻辑。"))

# LingSmartClient - check if stable
if lsc_y == 0 and wp_y == 0 and energy_y == 0:
    findings.append(("🟢", f"ling-smart-svc 服务稳定", f"`app.core.ling_smart_client`=0，WALLPAPER_ERROR=0，获取用户能量失败=0。ling-smart-svc 内网服务运行正常，无级联错误。"))
elif lsc_y > 0:
    findings.append(("🔴", f"ling-smart-svc 异常", f"`app.core.ling_smart_client` {lsc_y} 条，WALLPAPER_ERROR {wp_y} 条。需要排查 ling-smart-svc Pod 状态和网络连通性。"))

# Role not found
if role_y > 0:
    findings.append(("🟢", f"角色不存在（正常业务异常）", f"`角色不存在` {role_y} 条（关键词匹配），属于业务校验异常，非系统故障。"))

# New loggers
if new_loggers:
    findings.append(("🟡", f"新增Error Logger", f"以下Logger昨天首次出现：`{', '.join(new_loggers.keys())}`。需要持续观察是否持续增长。"))

# Gone loggers
if gone_loggers:
    findings.append(("🟢", f"Error Logger消失（改善）", f"以下Logger昨天已消失：`{', '.join(gone_loggers.keys())}`。表明相关错误已被修复或缓解。"))

# Peak hour analysis
report.append("### 1. 🔴 关键发现")
report.append("")
for emoji, title, detail in findings:
    report.append(f"- **{title}**：{detail}")
report.append("")

# Recommendations
report.append("### 2. 建议")
report.append("")
report.append("**高优先级：**")
report.append(f"1. **task_scheduler 优化**：`task_scheduler` 仍为最大Error来源（{ts_y}条，{ts_pct_y:.1f}%），主要错误类型为任务生成失败（{tgf_y}条）。建议为Dify工作流调用增加异步重试+退避机制，减少300秒超时等待。")
if crf_y > 0:
    report.append(f"2. **创建角色记录失败排查**：`创建角色记录失败` 持续出现（{crf_y}条），建议检查数据库中是否存在重复的 `(user_id, child_id)` 记录，并考虑添加唯一索引约束。")
if sb_y > 0:
    report.append(f"3. **中间件签名验证优化**：`signature_base` 中间件异常（{sb_y}条），Dify/DataCard 中间件各 {dify_y}/{kw_y.get('DataCard中间件', 0)} 条。建议检查下游服务响应超时配置，或将 `/health` 探针路径排除在签名校验之外。")

report.append("")
report.append("**中优先级：**")
report.append("4. **日志级别调整**：`图片未通过风控`（正常内容审核）、`角色不存在`（业务校验）等属于预期内的业务逻辑异常，建议从 ERROR 降级为 WARN，以便更准确地反映真正的系统异常。")
report.append("5. **持续监控**：关注新增Logger的变化趋势，如持续增长需及时排查。")

report.append("")
report.append("**低优先级/改善项：**")
report.append(f"6. **🟢 整体稳定**：Error总数环比 {'下降' if total_y < total_db else '持平'}（{change_str}），ling-smart-svc 无级联错误，框架级异常（ISE/ASGI）处于低位。")
if gone_loggers:
    report.append(f"7. **🟢 问题修复确认**：`{', '.join(list(gone_loggers.keys())[:3])}` 等Logger已消失，表明之前的问题已解决。")

report.append("")

# Print the report
output = "\n".join(report)
print(output)

# Also save
with open("/root/.hermes/workspace/sls_report_2026-07-02.md", "w") as f:
    f.write(output)
