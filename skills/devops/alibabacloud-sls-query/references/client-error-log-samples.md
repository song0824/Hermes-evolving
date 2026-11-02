# lingos-online-client-error Actual Log Samples

Top error categories with actual log content for quick identification. Data from 7-day scan 2026-06-17 to 2026-06-24.

## 1. 连接被关闭 / AbortedException — 12,781条 (28%)

**容器**: lingos-client | **命名空间**: lingos-online-new

```
ERROR reactor.core.publisher.Operators - Operator called default onErrorDropped
reactor.core.Exceptions$ErrorCallbackNotImplemented: reactor.netty.channel.AbortedException: Connection has been closed BEFORE send operation
Caused by: reactor.netty.channel.AbortedException: Connection has been closed BEFORE send operation
	at reactor.netty.channel.AbortedException.beforeSend(AbortedException.java:59)
	at com.ling.os.chat.core.client.WSClient.lambda$init$6(WSClient.java:67)
```

**根因**: WSClient 发起 WebSocket 连接时对端已关闭。客户端断连后连接未优雅清理，大量堆积。

---

## 2. JDBC连接池耗尽 (Druid) — 5,196条 (11%)

**容器**: lingos-admin | **命名空间**: lingos-online-pre

```
ERROR o.s.s.s.TaskUtils$LoggingErrorHandler - Unexpected error occurred in scheduled task
org.mybatis.spring.MyBatisSystemException: nested exception is org.apache.ibatis.exceptions.PersistenceException: 
### Error querying database.  Cause: org.springframework.jdbc.CannotGetJdbcConnectionException: Failed to obtain JDBC Connection; nested exception is com.alibaba.druid.pool.GetConnectionTimeoutException: wait millis 60000, active 0, maxActive 20, creating 0, createErrorCount 2
### The error may exist in .../ScheduleJobsMapper.java
### The error may involve com.ling.os.schedule.core.infrastructure.mapper.ScheduleJobsMapper.selectList
```

**根因**: Druid 连接池 maxActive=20 太小，定时任务查 ScheduleJobs 表时集中触发打满，等60秒超时。

---

## 3. 消息处理异常 (ContentSecurityException) — 4,355条 (10%)

**容器**: lingos-client | **命名空间**: lingos-online-new

```
ERROR c.l.os.chat.share.utils.LoggerUtils - ...消息处理异常: null null
com.ling.os.chat.core.exception.ContentSecurityException: null
	at com.ling.os.chat.core.pipeline.security.InputSecurityCheckProcess$1.lambda$doProcess$2(InputSecurityCheckProcess.java:125)
```

**根因**: 聊天消息过输入安全审查被拦截，ContentSecurityException message 为 null，异常信息不清晰。

---

## 4. Spring启动失败 (routeLocator NPE) — 2,051条 (4%)

**容器**: lingos-proxy | **命名空间**: lingos-online-pre

```
ERROR o.s.boot.SpringApplication - Application run failed
org.springframework.beans.factory.BeanCreationException: Error creating bean with name 'routeLocator' defined in class path resource [com/ling/os/ProxyRouteConfig.class]: Bean instantiation via factory method failed; nested exception is java.lang.NullPointerException
```

**根因**: ProxyRouteConfig.routeLocator() 抛 NPE，Gateway 启动失败循环重启。

---

## 5. TTS转换失败 — 80+条

**容器**: lingos-client | **命名空间**: lingos-online-new

```
ERROR c.l.o.t.c.i.tts.TTSProvider - [TTS] 请求TTS转换失败:
参数: TTSParameter(...options=TTSOptions(tts_agent=vocengine_S_puEpT9aq1...), text=但要是蜇别的昆虫，)
响应: TTSResult(errno=2007001006, errmsg=第三方服务异常, debug=Post "https://openspeech.bytedance.com/api/v3/tts/unidirectional": context deadline exceeded)
```

另一例：
```
响应: TTSResult(...debug=request error, status: 502, data=null)
```

**根因**: 火山引擎 TTS API 超时或返回502。

---

## 6. Base64解码异常 — 80条

**容器**: lingos-client | **命名空间**: lingos-online-new

```
ERROR c.l.os.chat.share.utils.LoggerUtils - ...消息处理异常:Illegal base64 character 5f null null
java.lang.IllegalArgumentException: Illegal base64 character 5f
	at java.base/java.util.Base64$Decoder.decode0(Base64.java:746)
	at com.ling.os.common.utils.Base64Utils.decode(Base64Utils.java:12)
	at com.ling.os.file.share.application.cmd.SimpleBase64UploadFileCmd.getData(SimpleBase64UploadFileCmd.java:11)
	at com.ling.os.chat.core.pipeline.file.DifyUploadProcess.lambda$doProcess$1(DifyUploadProcess.java:82)
```

**根因**: 文件上传时 Base64 数据含非法字符 `0x5f`（下划线 `_`），Base64Utils.decode 未做容错。

---

## 7. 大模型生成开场白失败

**容器**: lingos-admin | **命名空间**: lingos-online-new

```
ERROR c.l.o.s.c.a.SpecialPrologueGenerateImpl - 调用大模型生成lingos开场白发生错误,
rule: SpecialPrologueRulePO(name=儿童节, type=NORMAL, prompt=今天是儿童节, ...)
llmparam: IpAgentConfigInfoDTO(ipId=121769, defaultAgentKey=app-38x97KOHmZ..., prompt=你是埃隆马斯克...)
```

**根因**: 儿童节特殊开场白 Prompt 超长（包含完整人设），大模型 API 调用失败。
