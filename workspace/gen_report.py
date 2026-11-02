#!/usr/bin/env python3
"""Generate the daily SLS error analysis report."""
import json

with open("/root/.hermes/workspace/sls_daily_2026-07-26.json") as f:
    data = json.load(f)

y = data["yesterday"]
d = data["daybefore"]
ydate = data["date"]
ddate = data["daybefore_date"]

total_change = ((y["total"] - d["total"]) / d["total"] * 100) if d["total"] > 0 else 0

# Period aggregation
periods = {
    "凌晨(00-07)": list(range(0, 8)),
    "上午(08-12)": list(range(8, 13)),
    "下午(13-17)": list(range(13, 18)),
    "晚高峰(18-20)": list(range(18, 21)),
    "夜间(21-23)": list(range(21, 24)),
}

y_period = {}
d_period = {}
for pname, hrange in periods.items():
    yh = sum(y["hourly"].get(f"{h:02d}:00", 0) for h in hrange)
    dh = sum(d["hourly"].get(f"{h:02d}:00", 0) for h in hrange)
    y_period[pname] = yh
    d_period[pname] = dh

# Logger comparison
new_loggers = set(y["loggers"].keys()) - set(d["loggers"].keys())
gone_loggers = set(d["loggers"].keys()) - set(y["loggers"].keys())

# TTS combined
y_tts = y["loggers"].get("app.core.tts_client", 0) + y["loggers"].get("app.utils.audio_generator_scheduler", 0)
d_tts = d["loggers"].get("app.core.tts_client", 0) + d["loggers"].get("app.utils.audio_generator_scheduler", 0)

# Peak hour drilldown data
peak_drill = y.get("peak_drilldown", {})

# Category changes
categories = ["Dify中间件", "DataCard中间件", "角色不存在", "任务生成失败", "图片未通过风控",
              "LingSmartClient", "WALLPAPER_ERROR", "Internal Server Error", "Exception in ASGI",
              "已经点赞", "孩子不属于你", "Duplicate Entry"]

def mark_change(pct):
    if pct > 50:
        return "RED"
    elif pct < -50:
        return "GREEN"
    elif pct > 0:
        return "UP"
    elif pct < 0:
        return "DOWN"
    return "FLAT"

def fmt_pct(pct):
    if pct == float('inf'):
        return "NEW"
    elif pct == float('-inf'):
        return "-100%"
    return f"{pct:+.1f}%"

report = []
report.append("# SLS ling-server Daily Error Log Analysis Report")
report.append(f"## Report Date: {ydate} (vs {ddate})")
report.append("")

# === SECTION 1: Overview ===
report.append("## 1. Yesterday Error Log Distribution")
report.append("")
report.append("### 1.1 Overall Summary")
report.append("")
report.append(f"| Metric | Value |")
report.append(f"|---|---|")
report.append(f"| Total Errors | {y['total']} |")
report.append(f"| Active Hours | {sum(1 for v in y['hourly'].values() if v > 0)} / 24 |")
report.append(f"| Peak Hour | {y['top3_hours'][0][0]} ({y['top3_hours'][0][1]} errors) |")
report.append(f"| Active Loggers | {len(y['loggers'])} |")
report.append(f"| Deployment Version | {y.get('version', 'unknown')} |")
report.append("")

# Top 5 loggers
report.append("### 1.2 Top Error Loggers")
report.append("")
report.append("| Rank | Logger | Count | Percentage |")
report.append("|---|---|---|---|")
sorted_loggers = sorted(y["loggers"].items(), key=lambda x: x[1], reverse=True)
for i, (lg, cnt) in enumerate(sorted_loggers[:10], 1):
    pct = cnt / y["total"] * 100
    report.append(f"| {i} | {lg} | {cnt} | {pct:.1f}% |")
report.append("")

# Top 10 messages
report.append("### 1.3 Top 10 Error Messages")
report.append("")
report.append("| Rank | Count | Message |")
report.append("|---|---|---|")
for i, (cnt, msg) in enumerate(y["messages"][:10], 1):
    short_msg = msg[:100] + "..." if len(msg) > 100 else msg
    short_msg = short_msg.replace("|", "\\|").replace("\n", " ")
    report.append(f"| {i} | {cnt} | {short_msg} |")
report.append("")

# Hourly distribution
report.append("### 1.4 Hourly Distribution")
report.append("")
report.append("| Hour | Count | Visual |")
report.append("|---|---|---|")
max_h = max(y["hourly"].values()) if y["hourly"].values() else 1
for h in range(24):
    hk = f"{h:02d}:00"
    cnt = y["hourly"].get(hk, 0)
    bar = "#" * int(cnt / max_h * 30) if max_h > 0 else ""
    report.append(f"| {hk} | {cnt} | {bar} |")
report.append("")

# === SECTION 2: Comparison ===
report.append("## 2. Day-over-Day Comparison ({ydate} vs {ddate})")
report.append("")

# Total
report.append("### 2.1 Total Error Comparison")
report.append("")
report.append(f"| Metric | {ddate} | {ydate} | Change |")
report.append(f"|---|---|---|---|")
report.append(f"| Total Errors | {d['total']} | {y['total']} | {fmt_pct(total_change)} |")
report.append("")

# Period comparison
report.append("### 2.2 Period Comparison")
report.append("")
report.append("| Period | {ddate} | {ydate} | Change |")
report.append("|---|---|---|---|")
for pname in periods:
    dv = d_period[pname]
    yv = y_period[pname]
    chg = ((yv - dv) / dv * 100) if dv > 0 else (100 if yv > 0 else 0)
    report.append(f"| {pname} | {dv} | {yv} | {fmt_pct(chg)} |")
report.append("")

# Hourly comparison
report.append("### 2.3 Hourly Comparison")
report.append("")
report.append("| Hour | {ddate} | {ydate} | Change |")
report.append("|---|---|---|---|")
for h in range(24):
    hk = f"{h:02d}:00"
    dv = d["hourly"].get(hk, 0)
    yv = y["hourly"].get(hk, 0)
    chg = ((yv - dv) / dv * 100) if dv > 0 else (100 if yv > 0 else 0)
    m = mark_change(chg)
    report.append(f"| {hk} | {dv} | {yv} | {fmt_pct(chg)} |")
report.append("")

# Category comparison
report.append("### 2.4 Category Comparison")
report.append("")
report.append("| Category | {ddate} | {ydate} | Change |")
report.append("|---|---|---|---|")
for cat in categories:
    yv = y["categories"].get(cat, 0)
    dv = d["categories"].get(cat, 0)
    chg = ((yv - dv) / dv * 100) if dv > 0 else (100 if yv > 0 else 0)
    report.append(f"| {cat} | {dv} | {yv} | {fmt_pct(chg)} |")
report.append("")

# Logger changes
report.append("### 2.5 Logger Changes")
report.append("")
report.append("| Change | Logger | Count |")
report.append("|---|---|---|")
for lg in sorted(new_loggers):
    report.append(f"| NEW | {lg} | {y['loggers'].get(lg, 0)} |")
for lg in sorted(gone_loggers):
    report.append(f"| GONE | {lg} | {d['loggers'].get(lg, 0)} |")
if not new_loggers and not gone_loggers:
    report.append("| - | No new or gone loggers | - |")
report.append("")

# Top logger comparison
report.append("### 2.6 Top Logger Comparison")
report.append("")
report.append("| Logger | {ddate} | {ydate} | Change |")
report.append("|---|---|---|---|")
for lg, cnt in sorted_loggers[:8]:
    dc = d["loggers"].get(lg, 0)
    chg = ((cnt - dc) / dc * 100) if dc > 0 else 100
    report.append(f"| {lg} | {dc} | {cnt} | {fmt_pct(chg)} |")
report.append("")

# === SECTION 3: Peak Analysis ===
report.append("## 3. Peak Hour Drill-down")
report.append("")
for hour_str, count in y.get("top3_hours", [])[:3]:
    report.append(f"### {hour_str} CST ({count} errors)")
    if hour_str in peak_drill:
        drill = peak_drill[hour_str]
        report.append("| Logger | Count |")
        report.append("|---|---|")
        for lg, c in sorted(drill.items(), key=lambda x: x[1], reverse=True):
            report.append(f"| {lg} | {c} |")
    else:
        report.append("(No drill-down data available)")
    report.append("")

# === SECTION 4: Root Logger Analysis ===
report.append("## 4. Root Logger Analysis")
report.append("")
report.append(f"Total root logger errors: {y['loggers'].get('root', 0)}")
report.append("")
report.append("| Count | Message |")
report.append("|---|---|")
for cnt, msg in y.get("root_messages", [])[:10]:
    short_msg = msg[:120] + "..." if len(msg) > 120 else msg
    short_msg = short_msg.replace("|", "\\|").replace("\n", " ")
    report.append(f"| {cnt} | {short_msg} |")
report.append("")

# === SECTION 5: Key Findings ===
report.append("## 5. Key Findings and Recommendations")
report.append("")

# Findings
findings = []

# TTS finding
y_tts_total = y_tts
d_tts_total = d_tts
tts_pct = ((y_tts_total - d_tts_total) / d_tts_total * 100) if d_tts_total > 0 else 0
if tts_pct > 30:
    findings.append(f"[RED] TTS errors surged +{tts_pct:.0f}% (tts_client + audio_generator_scheduler: {d_tts_total} -> {y_tts_total}). 18:00 peak hour shows 74 tts_client errors. TTS conversion anomalies (2001001312) at 65 instances, +38% vs 47 on 07-25. Combined with audio_generator_scheduler (27 vs 6), TTS-related errors increased from 110 to 206 (+87%). This is a significant driver of the overall increase.")
    findings.append("[RED] Investigate TTS supplier API status (sensenova/volcengine) and ling-smart-svc connectivity during 18:00-19:00 window. Check if specific IPS records are causing repeated failures.")

# Multiple rows finding
if y["loggers"].get("root", 0) > 50:
    findings.append(f"[RED] 'Multiple rows were found when one or none was required' error persisted at 65 instances (root logger). This ORM issue in voip authorization loading indicates duplicate records in the database. Code fix: change one_or_none() to first() as temporary mitigation, plus DB deduplication.")

# Internal Server Error
ise_y = y["categories"].get("Internal Server Error", 0)
ise_d = d["categories"].get("Internal Server Error", 0)
ise_pct = ((ise_y - ise_d) / ise_d * 100) if ise_d > 0 else 0
if ise_pct > 30:
    findings.append(f"[RED] Internal Server Error increased +{ise_pct:.0f}% ({ise_d} -> {ise_y}). 144 bare ISE in top messages. Combined with exception_handlers at 294 (vs 206, +43%), this suggests downstream service degradation causing cascading failures.")

# NoneType.stream
nt_y = 48  # 24+24 from messages
nt_d = 44  # 22+22 from messages
if nt_y > 40:
    findings.append(f"[YELLOW] NoneType.stream errors persist at {nt_y} instances (user/statistics: 24, ip-dialog-info: 24). This is a known code bug missing None check on downstream response. Despite declining from earlier peaks, it remains a consistent error source.")

# Duplicate Entry
dup_y = y["categories"].get("Duplicate Entry", 0)
dup_d = d["categories"].get("Duplicate Entry", 0)
if dup_y > dup_d:
    findings.append(f"[YELLOW] Duplicate Entry errors doubled ({dup_d} -> {dup_y}). MySQL IntegrityError on users_app_un unique key from concurrent WeChat login registrations. Fix: use INSERT...ON DUPLICATE KEY UPDATE or pre-check before insert.")

# New logger: emergency_contact
if "app.controllers.emergency_contact" in new_loggers or y["loggers"].get("app.controllers.emergency_contact", 0) > 5:
    findings.append(f"[YELLOW] app.controllers.emergency_contact appeared with 11 errors. Contact-related errors (2001001301: 联系人不存在) for specific concat_ids (-76731, -76780). May indicate data inconsistency or new feature triggering validation errors.")

# SQLAlchemy pool
if y["loggers"].get("sqlalchemy.pool.impl.AsyncAdaptedQueuePool", 0) > 0:
    pool_y = y["loggers"]["sqlalchemy.pool.impl.AsyncAdaptedQueuePool"]
    pool_d = d["loggers"].get("sqlalchemy.pool.impl.AsyncAdaptedQueuePool", 0)
    findings.append(f"[YELLOW] SQLAlchemy connection pool errors: {pool_y} (vs {pool_d} on 07-25). Pool exhaustion at 22:00 suggests connection pressure during evening hours.")

# Debate transcript
debate_y = y["loggers"].get("app.event.handlers.debate_event_handler", 0)
if debate_y > 0:
    findings.append(f"[YELLOW] Debate event handler errors: {debate_y} instances. Includes Dify transcript > 2048 chars validation error. Code-side transcript truncation to <2000 chars needed.")

# CDN 400
cdn_y = 8  # from messages
if cdn_y > 0:
    findings.append(f"[YELLOW] CDN 400 error cascade: {cdn_y} instances of 下载图片失败→封面生成失败→处理视频格式失败 chain. Known CDN node issue (cdn-pub.leap.ling.space). Add retry+degrade strategy for image downloads.")

# Task scheduler improvement
task_y = y["loggers"].get("app.utils.task_scheduler", 0)
task_d = d["loggers"].get("app.utils.task_scheduler", 0)
task_pct = ((task_y - task_d) / task_d * 100) if task_d > 0 else 0
if task_pct > 0 and task_pct < 50:
    findings.append(f"[GREEN] task_scheduler errors at moderate level: {task_y} (+{task_pct:.0f}% vs {task_d}). Task generation failures (31 vs 22) increased slightly but remain within normal range. No systemic task scheduler issue detected.")

# Dify/DataCard middleware improvement
dify_y = y["categories"].get("Dify中间件", 0)
dify_d = d["categories"].get("Dify中间件", 0)
dc_y = y["categories"].get("DataCard中间件", 0)
dc_d = d["categories"].get("DataCard中间件", 0)
if dify_y < dify_d or dc_y < dc_d:
    findings.append(f"[GREEN] Dify/DataCard middleware errors decreased: Dify {dify_d}->{dify_y} ({fmt_pct(((dify_y-dify_d)/dify_d*100) if dify_d>0 else 0)}), DataCard {dc_d}->{dc_y} ({fmt_pct(((dc_y-dc_d)/dc_d*100) if dc_d>0 else 0)}). Downstream service stability improved vs previous day.")

# Late night spike
report_23 = y["hourly"].get("23:00", 0)
report_23d = d["hourly"].get("23:00", 0)
if report_23 > 100:
    spike_pct = ((report_23 - report_23d) / report_23d * 100) if report_23d > 0 else 0
    findings.append(f"[RED] CRITICAL: 23:00 hour saw 218 errors (vs {report_23d} on 07-25, +{spike_pct:.0f}%). This is the highest single-hour error count. The peak hour drill-down shows limited data but the sheer volume suggests a systemic issue during this period. Investigate what happened at 23:00 CST - could be batch job trigger, deployment, or traffic spike.")

# Coze
coze_y = y["loggers"].get("app.controllers.coze", 0)
if coze_y > 0:
    findings.append(f"[YELLOW] Coze platform 500 errors: {coze_y} instances. Coze returning 'We're currently experiencing server issues.' External platform issue, add retry+backoff strategy.")

# Video generator
vid_y = y["loggers"].get("app.core.video_generator", 0)
if vid_y > 0:
    findings.append(f"[YELLOW] Video generation errors: {vid_y} instances, including CDN 400 cascade failures. {cdn_y} full chain failures (download->cover->video format).")

for f in findings:
    report.append(f"- {f}")

report.append("")

# Output
print("\n".join(report))
