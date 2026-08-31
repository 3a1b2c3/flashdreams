# LingBot Session Changes (2026-08-31 → 2026-09-01)

Summary of everything changed in this session, across `integrations/lingbot`
and the shared `flashdreams` WebRTC serving infra it depends on.

## Setup / launch scripts (`integrations/lingbot/`)

- **`setup_lingbot_v2.sh`**
  - `python -m venv` failed on boxes without a bare `python` binary (Debian/Ubuntu ship only `python3`). Now falls back to `python3` if `python` isn't found.
  - Step 6 (`pip install -e ...`) used `--no-deps`, which meant `flashdreams`'s own core dependencies (`boto3`, `botocore`, `einops`, `filelock`, `ftfy`, `huggingface-hub`, `nvidia-ml-py`, `psutil`, `pyyaml`, `safetensors`, `tqdm`, `urllib3`, ...) never got installed and had to be hand-listed in step 5 — a list that had drifted out of sync, causing a `ModuleNotFoundError` whack-a-mole at runtime. Dropped `--no-deps`; pip now resolves them automatically without disturbing the already-installed pinned torch/tyro/transformers versions.
- **`run_direct.py`**: added a `--runner` flag (looked up via `lingbot.config.RUNNER_CONFIGS`) so any shipped runner slug can be selected. This script exists specifically because `flashdreams-run`'s tyro-based CLI registry is broken in this environment, so `--runner` is the only way to pick a non-default config here.
- **`run_light.sh`** (new): same as `run.sh` but runs `lingbot-world-fast-taehv-window15-sink3` — `window_size_t=15` (vs. the default's 63) + LightTAE decoder, for GPUs that OOM on the default config's larger KV cache.

## Scene presets (`lingbot/webrtc/web/adapter.js`, `SCENE_PRESETS.md`)

- 5 built-in presets, **Dragon** auto-selected as default on page load:
  1. **Dragon** — the app's existing example-00 default scene, given a name + the real `DEFAULT_TEXT_EVENTS` (Portal/Storm/Fireworks, from `session.py`, also on `main`) + Jump.
  2. **Jet Ski Cruise** (original preset, Superman event removed)
  3. **Noir Alley Combat** (new; Enemies Appear/Attack + Sirens Approach removed after initial add)
  4. **Water Blaster** (new)
  5. **Circuit Racer** (new; Drift + DRS Boost removed after initial add)
  - GTA Street Cruise and Rodeo Bull Ride were added, then removed and replaced with Noir Alley Combat / Water Blaster per request.
  - Every preset has a **Jump** event, sourced from the original `jumpPrompt` field in each REACTOR case JSON (custom-written for Dragon, which has no source file).
- Preset images are hotlinked `https://raw.githubusercontent.com/...` URLs (from `Robbyant/lingbot-world-v2` and `3a1b2c3/js-sdk`'s `examples` branch) — not committed as binaries in this repo (a local-asset attempt was tried and reverted per explicit instruction to keep using GitHub-hosted images). Local backup copies + the original richer `lib/lingbot-cases/*.json` scene defs (used as source material when writing the flat prompt+events versions) are kept for reference under `lingbot/webrtc/web/assets/` and `assets/sources/`.
- UX/behavior fixes:
  - Quick Start dropdown no longer resets to the placeholder after picking a preset.
  - Picking a preset now updates the image **preview** immediately, not just the URL text field.
  - **Fixed a real bug**: `beforeConnect()` never passed `includeFirstFrame: true` to the upload call, so a preset's image was silently never sent to the server on connect — every session always started with the server's own default image regardless of what was selected. Fixed.
  - Digit keys **1-9** now jump straight to the corresponding preset (ignored while typing in a field); dropdown options show the hotkey number (`"1. Dragon"`, etc.).
  - `?preset=<slug>` URL param (slug = lowercased name, spaces → hyphens) deep-links directly to a specific preset, e.g. `?preset=water-blaster`.
  - Preset selection now logs to the Client Logs panel (`preset selected: <name>`).

## Shared WebRTC serving infra (`flashdreams/flashdreams/serving/webrtc/`, `runtime/demo/`)

These fix the `409: A Lingbot session is already active.` issue that required a manual server restart to clear, in three layers (found one bug per layer by tracing why the previous fix didn't fully resolve it):

- **`manager.py` — `create_answer()`**: a new connect attempt now always preempts/closes a stuck `_active_session` instead of raising 409 forever.
- **`manager.py` — `ManagedWebRTCSession.close()`**: fixed a real leak — the admission-slot reservation was only released if `generation_task.done()`, which is `False` when `close()` is called *from within* the generation task's own cleanup (e.g. after a crash) — so it silently never released. Now always releases.
- **`manager.py` / `run_modes.py` / `host.py`**: added `SingleSessionAdmissionPolicy.force_release()` and `RuntimeHost.force_healthy()`, wired into `_create_answer_with_runtime_ready_locked()` as a retry-once fallback. This is the "hacky" layer, deliberately bypassing an intentional permanent safety latch (`RuntimeHost.mark_unhealthy()`, tripped when session cleanup itself fails/times out after a crash — plausible after the CUDA OOMs hit today, per `drivers.py`). Real fix for *that* is avoiding the OOM in the first place (use `run_light.sh`, consider `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`), not bypassing the latch.
- **`server.py` — `/healthz`**: now also returns `pid`, `process_started_at`, `process_uptime_s`, so a restart can be confirmed from a browser alone (no SSH needed).
- **`request_session.js`** (shared connect page, used by every model's demo, not just lingbot):
  - `?manual` query param disables auto-connect-on-load (default behavior unchanged for everyone else); fixed a bug where the Connect button stayed permanently disabled in this mode.
  - The Connect button now toggles to **"Disconnect"** once connected, and clicking it does a proper clean teardown (was previously only reachable via closing the tab).

## Known remaining issue

- Server-side, a live session's advertised event catalog can echo back the server's `DEFAULT_TEXT_EVENTS` (Portal/Storm/Fireworks) instead of the connected preset's own events in some cases (seen live on Circuit Racer). Root cause not yet found — `renderEventControls()` client-side reads correctly from `initialScene.event_catalog`, so the mismatch is upstream, most likely in what `/api/session/input` echoes back or in `_shared_webrtc_spec`'s `session_input.text_events` handling.
