---
name: video-transcript-via-vision
description: Transcribe videos by extracting frames and using Vision AI to read subtitles/text overlays. Fallback when audio transcription (Whisper) is unavailable due to network restrictions or model download failures.
version: 1.0.0

---

# Video Transcription via Vision AI

Fallback approach for transcribing videos when Whisper/audio transcription is unavailable.

## When to use

- Whisper/faster-whisper cannot download models (network unreachable)
- Video has clear text overlays or subtitles burned in
- Educational, tutorial, or informational videos with on-screen text

## Steps

### 1. Try audio transcription first

```bash
# Try faster-whisper (already installed)
python3 -c "from faster_whisper import WhisperModel; model = WhisperModel('base', device='cpu', compute_type='int8'); segments, info = model.transcribe('video.mp4', language='zh'); print(''.join(s.text for s in segments))"
```

If this fails with network/model errors, proceed to vision approach.

### 2. Extract frames with ffmpeg

```bash
mkdir -p /tmp/frames
# Extract 1 frame per second
ffmpeg -i video.mp4 -vf "fps=1" /tmp/frames/frame_%04d.jpg -y
```

For a 2-3 minute video, this yields ~120-180 frames.

### 3. Sample frames for vision analysis

Don't analyze every frame — sample every 5-10 frames:

```python
import os
frames = sorted(os.listdir('/tmp/frames'))
# Sample every 10th frame
sampled = frames[::10]
```

### 4. Use vision_analyze on sampled frames

For each sampled frame, call:
```
vision_analyze(image_url="/tmp/frames/frame_XXXX.jpg", question="What Chinese text/subtitles are visible? Transcribe exactly.")
```

### 5. Compile into transcript

- Merge all extracted text in chronological order
- Group by topic/section headers visible in frames
- Add timestamps based on frame numbers (frame_N = N seconds)
- Include a summary table of key points

## Pitfalls

- **Network restrictions**: Whisper model download from HuggingFace fails with "Network is unreachable" — this is the primary trigger for this fallback
- **faster-whisper**: Already installed in the environment, but models still require network download
- **vision_analyze**: Does NOT support video files directly — only image files
- **Frame sampling**: Too dense = too many API calls; too sparse = miss subtitles. 1fps extraction + every 10th frame analysis is a good balance
- **Text clarity**: Works best for videos with large, persistent text overlays. Fast-moving or small text may be missed

## Verification

- Cross-check that the compiled transcript flows logically
- Ensure all major section headers were captured
- Look for gaps where subtitles might have been missed between sampled frames