**SLS QPS**：leap-online/cn-shanghai。条件详见 `alibabacloud-sls-query` skill。
§
**群组回复规则**：
- **单独 @我**：必须回复并处理任务。
- **@all**：**保持绝对静默**，不发送任何回复（连"保持静默"这几个字也不要输出）。
§
**Database Query (lingos_new, readonly)**: `list_db_connections` → `save_db_knowledge`。
⚠️ `query_sql` 限制：拦截 DELETE/CREATE 子串；datetime 列 SELECT 返回 null（WHERE 正常）；替代：`UNIX_TIMESTAMP(datetime_col)`。小方机激活量查 `robots_attachments` 表 `active=1 AND actived_at`。
§
**飞书群组**：4️⃣【搞钱】AI说画投影互动剧场INKO-产研供内销群，chat_id: oc_e64407d3de99d94988d66ce743498097
§
**抖店登录**：
- 通过 OpenVPN 隧道（出口 IP 114.242.33.251）绕过 2046 风控
- 页面加载后需：关闭弹窗 → 点右上角二维码图标 → 等待抖店APP扫码
- 扫码完成后只截图发状态，不执行任何操作
- Cookie路径：`~/.hermes/cache/fxg_storage_state.json`
- 订单API脱敏（1**********），需开放平台API解密
§
test群 oc_8b8978c0510660ec4da3c52ebc7bb9a3。多个bot：hermes(ou_41e5c8ebbe0ea74578cb06ba106db7b3)、人机openclaw(ou_129dd5839056b1b78729efe53e91a764)。@没反应先确认@的是哪个。
§
**飞书 API**：App ID: `cli_a97b1e4633f99cb0`。Bitable Create/Write。云文档/wiki 仅 readonly。新文件给群/用户开 full_access。
§
生图：DashScope wan2.6-t2i（北京）。Key 见 `.hermes/.env`。Workspace: `llm-2mnugdosx628stt0`。Gemini 备用。
§
**技术周会**：脚本 `scripts/weekly_tech_meeting.py`，cron `468a36759729`（周五 9:00）。模板 `KtOLd1e7CoSXkNxgF7jcDiI7nrd`，wiki space `7612892588537892047`，父节点 `AAGlw95lZi4sUqk78vzc7mkHnIb`，通知群为研发运维群 `oc_611b7861968a34f8c2f538f67410b629`。先创建 wiki 节点（不传 obj_token）→ 写 blocks。文档权限给研发运维群和 test 群。加急大卫 `ou_dfc3579b6b0ced44f7745f24ace77b73`。催填脚本 `scripts/weekly_report_reminder.py`（周一 11:00），认 `YYYY-MM-DD` 与 `YYYY年M月D日` 标题，@ 未填的人发到研发运维群。
§
研发团队组织架构（R&D）：愚者已离职，账号已停用，不再授权、不加急、不 @。架构师大卫、安卓(梧桐/天璇/洛基/白羊/猎户)、JAVA黑洞、运维天行者、后端(海晨/周行/六芒星/螺旋)、AIGC云天明、AI南斗/星轨、Flutter(辰星/启元)、服务端九九、测试(闪电/大羊星/白洞/彗星/开拓者)。待招：golang后端、AI算法、算法实习生、外包测试、Linux工程师。团队使用代号/昵称文化。
§
**项目多维表格数据源**：
- 国内OTA：wiki `BqLuwv4fNiAUERkLG2Yc6YO0nxd`，bitable `JmEHb9orfaOmYssOwETcNncYnWd`，table `tbl9c4NAOuRuIPpt`
- 海外Luka：wiki `WJ2Pw3xMGiRq8Sk4nDqccXXJn7b`，bitable `JceAbET1Jax8TtstyNUcbRBunxd`，table `tblOiYO57m0h8zk2`
**需求文档分析偏好**：按人员聚合，显示父节点上下文（【父】→子需求），含起止时间/周期，仅统计未完成（排除Completed），按未完成数降序+负载等级，重新生成时创建新文档，给大卫（ou_dfc3579b6b0ced44f7745f24ace77b73）开 full_access
§
**Git 远程**：`origin` → GitLab `gitlab.ling.ai:10080/songzihang/Hermes-evolving.git`；`github` → GitHub `github.com/song0824/Hermes-evolving.git`。