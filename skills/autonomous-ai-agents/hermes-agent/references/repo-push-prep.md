# Preparing Hermes Repo for Remote Push

## Secret Patterns to Scan Before Push

These patterns triggered GitHub's push protection during a session:

| Pattern | Location | Fix |
|---------|----------|-----|
| `app_secret` in config.yaml | Line ~484 | Replace with `${FEISHU_APP_SECRET}` |
| `app_id` in config.yaml | Line ~483 | Replace with `${FEISHU_APP_ID}` |
| `FEISHU_APP_SECRET = "..."` in Python scripts | scripts/*.py | Replace with `os.environ.get("FEISHU_APP_SECRET", "")` |
| `FEISHU_APP_ID = "..."` in Python scripts | scripts/*.py | Replace with `os.environ.get("FEISHU_APP_ID", "")` |

## GitLab / Internal Registry Push

When pushing to an internal GitLab (e.g. `gitlab.ling.ai:10080`):

- DNS may resolve but the port may be unreachable from outside the VPN
- **Verify reachability before pushing**: `curl -sI --connect-timeout 5 http://gitlab.ling.ai:10080`
- If unreachable, configure the remote anyway and push when on the correct network:
  ```bash
  git remote add origin http://gitlab.ling.ai:10080/owner/repo.git
  # Push when VPN/inner network is active:
  git push -u origin main --force
  ```
- SSH (port 22) may also be unreachable — use HTTP fallback

## Build Directory Pattern

```bash
BUILD_DIR=/tmp/hermes-push
mkdir -p "$BUILD_DIR"
cp -r hermes-agent/ hermes-webui/ skills/ scripts/ workspace/ memories/ "$BUILD_DIR"
cp config.yaml SOUL.md .gitignore "$BUILD_DIR"
# Clean caches, databases, sessions, logs, cron outputs
rm -rf "$BUILD_DIR"/hermes-agent/venv/ "$BUILD_DIR"/*/node_modules/
rm -rf "$BUILD_DIR"/cache/ "$BUILD_DIR"/sessions/ "$BUILD_DIR"/logs/
rm -rf "$BUILD_DIR"/cron/output/ "$BUILD_DIR"/rds/ "$BUILD_DIR"/weixin/
rm -f "$BUILD_DIR"/*.db "$BUILD_DIR"/state.db* "$BUILD_DIR"/auth.json
```
