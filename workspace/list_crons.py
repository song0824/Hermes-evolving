import json

data = json.load(open("/root/.hermes/cron/jobs.json"))
for j in data.get("jobs", []):
    info = {
        "id": j["id"],
        "name": j.get("name", ""),
        "script": j.get("script", ""),
        "prompt": j.get("prompt", "")[:300] if j.get("prompt") else ""
    }
    print(json.dumps(info, ensure_ascii=False, indent=2))
    print("---")
