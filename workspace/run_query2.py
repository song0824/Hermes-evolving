import subprocess
import json
import sys

prompt = '''You are a data analysis agent. Do ONLY the following steps and output the result as JSON:

1. Use query_sql tool with connection_id="lingos_new" to run:
SELECT CAST(date AS CHAR) as dt, COUNT(*) as total, COUNT(CASE WHEN status=2 THEN 1 END) as success, COUNT(CASE WHEN status=3 THEN 1 END) as fail, COUNT(CASE WHEN status=1 THEN 1 END) as ing, COUNT(DISTINCT child_id) as active_users FROM child_custom_role_task WHERE type=2 AND date = '2026-05-20'

2. Use query_sql tool with connection_id="lingos_new" to run:
SELECT CAST(date AS CHAR) as dt, COUNT(*) as total, COUNT(CASE WHEN status=2 THEN 1 END) as success, COUNT(CASE WHEN status=3 THEN 1 END) as fail, COUNT(CASE WHEN status=1 THEN 1 END) as ing, COUNT(DISTINCT child_id) as active_users FROM child_custom_role_task WHERE type=2 AND date = '2026-05-19'

3. Use query_sql tool with connection_id="lingos_new" to run:
SELECT t.title, c.template_id, COUNT(*) as cnt, COUNT(CASE WHEN c.status=2 THEN 1 END) as success, COUNT(CASE WHEN c.status=3 THEN 1 END) as fail FROM child_custom_role_task c LEFT JOIN child_task_template t ON c.template_id=t.id WHERE c.type=2 AND c.date = '2026-05-20' GROUP BY c.template_id ORDER BY cnt DESC LIMIT 10

4. Output ALL query results as a single JSON object with keys: yesterday, day_before, templates

Do NOT do anything else. Do NOT send any messages. Just output the JSON.'''

proc = subprocess.Popen(
    ["hermes", "chat", "-q", prompt, "--yolo", "-Q", "--ignore-rules"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

try:
    stdout, stderr = proc.communicate(timeout=300)
    print("STDOUT:", stdout[-5000:] if len(stdout) > 5000 else stdout)
    print("STDERR:", stderr[-2000:] if len(stderr) > 2000 else stderr)
    print("Return code:", proc.returncode)
except subprocess.TimeoutExpired:
    proc.kill()
    stdout, stderr = proc.communicate()
    print("TIMEOUT")
    print("STDOUT:", stdout[-3000:] if len(stdout) > 3000 else stdout)
    print("STDERR:", stderr[-1000:] if len(stderr) > 1000 else stderr)
