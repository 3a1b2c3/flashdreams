# WebRTC Prompt & Actor Commands Debug Logging

## Overview

Debug logging for Scene Prompt text field and actor commands (`/spawn`, `/clear-actors`) in the WebRTC UI.

**Files modified:**
- `integrations/omnidreams/omnidreams/webrtc/web/request_session.js` — Client-side logging (already existed)
- `integrations/omnidreams/omnidreams/webrtc/session.py` — Server-side debug logging (added)

## Enabling Debug Logging

### Option 1: Set LOGURU_LEVEL Environment Variable

```bash
# Before running WebRTC server:
set LOGURU_LEVEL=DEBUG

# Then run:
.\run_webrtc_server.sh
```

### Option 2: Add to run script (persistent)

Edit `run_webrtc_server.sh` or `run_webrtc_server.bat`:
```bash
export LOGURU_LEVEL=DEBUG  # or set LOGURU_LEVEL=DEBUG on Windows
python -m omnidreams.webrtc.server ...
```

### Option 3: Python code (if running programmatically)

```python
import logging
from loguru import logger

# Set global log level to DEBUG
logger.enable("omnidreams")
logger.configure(handlers=[{"sink": sys.stderr, "level": "DEBUG"}])
```

## Log Message Reference

### Prompt Events

**Received prompt from UI:**
```
[PROMPT-EVENT-RECV] event_id='heavy snow at night', state='trigger'
```
- `event_id` — The prompt text user entered
- `state` — Either 'trigger' (apply) or 'clear'/'release' (reset)

**Clearing/Resetting prompt:**
```
[PROMPT-EVENT] Clearing prompt, restored to scene default: 'sunny day'
```
- Triggered by Reset button or empty prompt

**Prompt unchanged (no-op):**
```
[PROMPT-EVENT] Prompt unchanged: 'heavy snow at night'
```
- User submitted same prompt twice; server skipped it

**Building text embeddings:**
```
[PROMPT-EVENT-BUILD] Building text embeddings for: 'heavy snow at night'
```
- Prompt is being converted to text embeddings

**Staging for start (no rollout yet):**
```
[PROMPT-EVENT-STAGE] No rollout yet, staging for start_generation
```
- Rollout hasn't produced a frame yet; prompt will be used when generation starts

**Swapping mid-stream:**
```
[PROMPT-EVENT-SWAP-START] Applying text prompts at chunk 42
```
- Applying prompt immediately to running generation

**Swap complete:**
```
[PROMPT-EVENT-SWAP-DONE] Swapped Omnidreams prompt in 12.5 ms (chunk=42): heavy snow at night
```
- Swap succeeded; timing and chunk index shown

### Actor Commands

**Received actor command:**
```
[ACTOR-CMD] Received: '/spawn car 12' (parsed: 'spawn')
```
- Command type detected and parsed

**Clearing actors:**
```
[ACTOR-CMD-CLEAR] Cleared 3 actors
```
- N actors removed from scene

**Parsing spawn command:**
```
[ACTOR-CMD-SPAWN] Parsing spawn command: '/spawn car 12 5.0 2.0'
```
- Spawn command detected

**Parsed spawn parameters:**
```
[ACTOR-CMD-SPAWN-PARAMS] preset=car, dist=12.0m, speed=5.0m/s, lateral=2.0m, yaw=0.0°
```
- Parameters extracted and validated

**Spawn complete (logger.info, not debug):**
```
Spawned actor car at 12.0 m ahead (speed 5.0 m/s, lateral 2.0 m); 1 active (chunk=42).
```

## Full Example: Prompt Swap Flow

**User enters prompt in UI and clicks Apply:**

Client logs (browser console):
```
[Omnidreams WebRTC][client] prompt sent: heavy snow at night
```

Server logs (terminal with `LOGURU_LEVEL=DEBUG`):
```
[PROMPT-EVENT-RECV] event_id='heavy snow at night', state='trigger'
[PROMPT-EVENT-BUILD] Building text embeddings for: 'heavy snow at night'
[PROMPT-EVENT-SWAP-START] Applying text prompts at chunk 42
[PROMPT-EVENT-SWAP-DONE] Swapped Omnidreams prompt in 8.3 ms (chunk=42): heavy snow at night
```

## Full Example: Spawn Actor Flow

**User clicks "Spawn car" button:**

Client logs:
```
[Omnidreams WebRTC][client] prompt sent: /spawn car 12
```

Server logs:
```
[ACTOR-CMD] Received: '/spawn car 12' (parsed: 'spawn')
[ACTOR-CMD-SPAWN] Parsing spawn command: '/spawn car 12'
[ACTOR-CMD-SPAWN-PARAMS] preset=car, dist=12.0m, speed=0.0m/s, lateral=0.0m, yaw=0.0°
Spawned actor car at 12.0 m ahead (speed 0.0 m/s, lateral 0.0 m); 1 active (chunk=42).
```

## Log Filtering

### Show only prompt events:

```bash
# Linux/Mac:
python -m omnidreams.webrtc.server ... 2>&1 | grep "PROMPT-EVENT"

# Windows (PowerShell):
python -m omnidreams.webrtc.server ... 2>&1 | Select-String "PROMPT-EVENT"
```

### Show only actor commands:

```bash
# Linux/Mac:
python -m omnidreams.webrtc.server ... 2>&1 | grep "ACTOR-CMD"

# Windows (PowerShell):
python -m omnidreams.webrtc.server ... 2>&1 | Select-String "ACTOR-CMD"
```

### Show timing info only:

```bash
# Linux/Mac:
python -m omnidreams.webrtc.server ... 2>&1 | grep "SWAP-DONE\|Spawned"

# Windows (PowerShell):
python -m omnidreams.webrtc.server ... 2>&1 | Select-String "SWAP-DONE|Spawned"
```

## Interpreting Timing

### Prompt swap latency

```
[PROMPT-EVENT-SWAP-DONE] Swapped Omnidreams prompt in 12.5 ms (chunk=42): ...
```

- **< 20 ms** — Excellent (should be typical)
- **20-50 ms** — Good
- **> 100 ms** — Slow; check if GPU is saturated or other tasks running

### Spawn latency

```
Spawned actor car at 12.0 m ahead ... (chunk=42).
```

- No explicit timing, but should be < 10 ms
- If missing `[ACTOR-CMD-SPAWN-PARAMS]`, parsing failed

## Troubleshooting

### No debug logs appearing

**Check:**
1. `LOGURU_LEVEL=DEBUG` is set before running server
2. Logs are going to stderr, not stdout
3. Prompt is actually being sent (check client browser console)

**Fix:**
```bash
# Explicitly enable debug:
set LOGURU_LEVEL=DEBUG
python -m omnidreams.webrtc.server ... 2>&1 | tee server.log
```

### Prompt swap timing very slow (> 500 ms)

**Likely causes:**
- GPU is busy with other tasks (check `nvidia-smi`)
- KV cache rebuild happening (expected on first swap)
- Model is running at high resolution (768p+ with large batch)

**Solution:**
- Reduce resolution or batch size
- Wait for GPU to finish other work
- Check if other processes are using GPU

### Actor spawn fails with "Unknown command"

**Check:**
- Spelling: `/spawn car` (not `/spawnt` or `spawn car`)
- Preset name: must be one of `car`, `cone` (check `ACTOR_PRESETS` in code)
- Order: preset comes first, then distance, speed, lateral

**Valid:**
```
/spawn car 12
/spawn car 12 5.0
/spawn car 12 5.0 2.0
/clear-actors
```

## Log Output Examples

### Successful prompt swap (from scene default to custom):

```
[PROMPT-EVENT-RECV] event_id='bright sunny day with blue sky', state='trigger'
[PROMPT-EVENT-BUILD] Building text embeddings for: 'bright sunny day with blue sky'
[PROMPT-EVENT-SWAP-START] Applying text prompts at chunk 5
[PROMPT-EVENT-SWAP-DONE] Swapped Omnidreams prompt in 6.2 ms (chunk=5): bright sunny day with blue sky
```

### Reset to scene default:

```
[PROMPT-EVENT-RECV] event_id='', state='clear'
[PROMPT-EVENT] Clearing prompt, restored to scene default: 'daytime highway'
```

### Prompt before rollout starts:

```
[PROMPT-EVENT-RECV] event_id='rain at night', state='trigger'
[PROMPT-EVENT-BUILD] Building text embeddings for: 'rain at night'
[PROMPT-EVENT-STAGE] No rollout yet, staging for start_generation
```

### Spawn car + cone + clear:

```
[ACTOR-CMD] Received: '/spawn car 12' (parsed: 'spawn')
[ACTOR-CMD-SPAWN] Parsing spawn command: '/spawn car 12'
[ACTOR-CMD-SPAWN-PARAMS] preset=car, dist=12.0m, speed=0.0m/s, lateral=0.0m, yaw=0.0°
Spawned actor car at 12.0 m ahead (speed 0.0 m/s, lateral 0.0 m); 1 active (chunk=10).

[ACTOR-CMD] Received: '/spawn cone 8' (parsed: 'spawn')
[ACTOR-CMD-SPAWN] Parsing spawn command: '/spawn cone 8'
[ACTOR-CMD-SPAWN-PARAMS] preset=cone, dist=8.0m, speed=0.0m/s, lateral=0.0m, yaw=0.0°
Spawned actor cone at 8.0 m ahead (speed 0.0 m/s, lateral 0.0 m); 2 active (chunk=11).

[ACTOR-CMD] Received: '/clear-actors' (parsed: 'clear-actors')
[ACTOR-CMD-CLEAR] Cleared 2 actors
```

## Related Code

- **Client JS:** `integrations/omnidreams/omnidreams/webrtc/web/request_session.js:446-474` (`sendPromptEvent()`)
- **Server Python:** `integrations/omnidreams/omnidreams/webrtc/session.py:728-763` (`_trigger_event_sync()`)
- **Actor handling:** `integrations/omnidreams/omnidreams/webrtc/session.py:765-844` (`_handle_actor_command_sync()`)

## Notes

- Debug logs use `logger.debug()` and won't appear unless `LOGURU_LEVEL=DEBUG`
- Info logs (`logger.info()`) always appear regardless of level
- Timing measurements are wall-clock (real elapsed time), not just computation
- Actor commands share the datachannel with prompts (anything starting with `/` is a command)
