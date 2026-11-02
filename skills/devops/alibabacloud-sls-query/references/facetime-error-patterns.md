# lingos-online-facetime Error Patterns

## Overview

FaceTime 服务使用 MCP Server 架构（`mcp.server.streamable_http_manager`, `mcp.server.lowlevel.server`），ERROR 日志包含大量框架级噪音，分析时需过滤。

## Error Classification

### 1. 火山模型参数错误（占比最大）
```
request model Parameter error, platform: volcengine,
model_name: doubao-seed-2-0-lite-260215,
message: Parameter error (Original: ArkBadRequestError: Error code: 400 -
  {'error': {'code': 'InvalidParameter',
   'message': 'The parameter `messages.content.image_url.url`
               specified in the request are not valid: image url is empty.
```
- **根因**：调用多模态模型时 `image_url` 为空
- **修复**：调用前加 `if not image_url: skip` guard
- **频率**：5/24=503, 5/25=130（5/25 可能部分修复或流量下降）

### 2. Stateless session crashed
```
logger: mcp.server.streamable_http_manager
message: Stateless session crashed
(no exception field)
```
- **根因**：客户端断连后会话未优雅清理
- **建议**：降级为 WARN 或静默处理
- **频率**：5/24=219, 5/25=94

### 3. received message timeout
```
received message timeout, stop consumer
```
- **根因**：消息队列消费超时
- **频率**：5/24=89, 5/25=78

### 4. exception from stream
```
logger: mcp.server.lowlevel.server
message: Received exception from stream: 
(no detail in message, no exception field)
```
- **频率**：5/24=21, 5/25=5

### 5. tool call failed
```
tool call failed, tool_name: layout_dify_workflow_drawing_artcard_3d,
error: Expecting ':' delimiter: line 1 column 10 (char 9)
```
- **根因**：Dify workflow tool 返回非法 JSON
- **涉及工具**：`layout_dify_workflow_drawing_artcard_3d`, `layout_libaicreate_v1`, `layout_dify_workflow_word_card`

## Analysis Tip

When analyzing facetime errors, filter out framework noise first:
```python
# Skip these as they are framework-level noise, not business errors
framework_noise = ["Stateless session crashed", "Received exception from stream",
                    "received message timeout", "Error in message router"]
# Focus on: Parameter error, tool call failed
```
