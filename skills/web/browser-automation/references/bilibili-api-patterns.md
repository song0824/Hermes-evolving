# Bilibili API Reference

## Video Info (no auth needed)
```
GET https://api.bilibili.com/x/web-interface/view?bvid=BV1mVM8zeEBW
```
Returns: title, desc, duration, cid, owner, pages[], tags, first_frame URL, dynamic, redirect_url

## Subtitle Check (no auth needed)
```
GET https://api.bilibili.com/x/player/v2?bvid=BV1mVM8zeEBW&cid=30516052964
```
Response field: `data.subtitle.subtitles` — empty array means no subtitles available.

## Tags (no auth needed)
```
GET https://api.bilibili.com/x/tag/archive/tags?bvid=BV1mVM8zeEBW
```

## Danmaku / Bullet Comments (no auth needed, zlib compressed)
```
GET https://comment.bilibili.com/{CID}.xml
```
Response is zlib-compressed XML. Decompress with `zlib.decompress()`.

## User Video Search (requires WBI signature, may fail)
```
GET https://api.bilibili.com/x/space/wbi/arc/search?mid={UP_ID}&pn=1&ps=5&order=pubdate
```
Often times out or requires signed parameters — not reliable.

## Anti-bot Patterns
- Direct page fetch via curl/urllib → **HTTP 412 Precondition Failed**
- yt-dlp → **HTTP 412 Precondition Failed**
- Bilibili video **must** be analyzed via browser playback
- Baidu/Sogou search → CAPTCHA — use Bilibili's own search (`search.bilibili.com/all?keyword=xxx`)

## Key Pattern: Video Analysis via Browser
```javascript
// Seek
var v = document.querySelector('video');
v.currentTime = 180;
v.play();

// Wait 5 seconds (in terminal: sleep 5)

// Pause and verify
var v = document.querySelector('video');
v.pause();
Math.round(v.currentTime) + 's'

// Then browser_vision(...)
```
