import json

with open("/root/.hermes/sessions/session_cron_050863eba4b6_20260520_170053.json") as f:
    session = json.load(f)

messages = session.get("messages", [])
for i, msg in enumerate(messages):
    role = msg.get("role", "")
    if role == "assistant":
        tc = msg.get("tool_calls", [])
        if tc:
            for call in tc:
                func = call.get("function", {})
                name = func.get("name", "")
                args = func.get("arguments", "")
                if "query_sql" in name or "execute_code" in name:
                    print(f"Msg {i}: {name}")
                    print(f"  Args: {args[:500]}")
                    print()
    elif role == "tool":
        name = msg.get("name", "")
        content = msg.get("content", "")
        if "query_sql" in name:
            print(f"Msg {i}: tool result for {name}")
            print(f"  Content: {content[:500]}")
            print()
