# OpenCLI Browser Integration

## opencli browser commands

```bash
opencli doctor                              # Check connection status
opencli browser <session> open <URL>         # Open page
opencli browser <session> state              # View element index
opencli browser <session> screenshot [path]  # Screenshot
opencli browser <session> click N            # Click element [N]
opencli browser <session> fill N 'text'      # Fill form
opencli browser <session> extract            # Extract page as Markdown
opencli browser <session> console            # View console logs
opencli browser <session> close              # Close tab
```

If extension fails to connect, `opencli browser` commands error out — fall back to Playwright (`browser_navigate` + `browser_console` + `browser_vision`).

## opencli douyin adapter limitation

The `opencli douyin` adapter targets `creator.douyin.com` (creator platform), **NOT** `fxg.jinritemai.com` (抖店 merchant backend). To operate 抖店 via opencli, use `opencli browser fxg <command>` generic browser mode only.

## Daemon port & SSH tunnel

The extension daemon listens on `127.0.0.1:19825`. For remote access:
```bash
ssh -L 19825:localhost:19825 root@<server-ip>
```

After loading the extension in Chromium, restart the daemon:
```bash
opencli daemon restart && opencli doctor
```
