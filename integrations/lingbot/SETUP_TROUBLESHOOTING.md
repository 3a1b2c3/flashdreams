# LingBot WebRTC setup — known issues and fixes

Working notes from getting `flashdreams-run` / `run.sh` running on a fresh
Linux venv (Python 3.12, CUDA 13.2). Update this file whenever a new
environment issue is found and fixed — this stack has repeatedly regressed
the same way across venv rebuilds.

## 1. `transformers` version must be `>=5.0,<6`

`flashdreams/pyproject.toml` requires `transformers>=5.0,<6`. Older setup
scripts pinned `transformers==4.40.0` / `4.45.0`, which predates the actual
requirement and breaks lazy imports like `UMT5EncoderModel` with a generic,
misleading error:

```
ModuleNotFoundError: Could not import module 'UMT5EncoderModel'. Are this
object's requirements defined correctly?
```

Fix: install `transformers>=5.0,<6` (see `setup_lingbot_v2.sh`).

**Gotcha:** this error message is generic — transformers' lazy-import
`__getattr__` swallows the real underlying exception. To see the real
cause, import the concrete submodule directly instead of the top-level lazy
attribute, e.g.:

```bash
python -c "import transformers.models.umt5.modeling_umt5 as m"
```

That surfaced a *second*, unrelated issue (see #2).

## 2. torch / torchaudio CUDA version mismatch

Installing `torchaudio` separately (not pinned to the same CUDA index as
`torch`) leaves it built against a different CUDA version than torch. This
gets imported transitively via `transformers.audio_utils` (imported by
`transformers.processing_utils`, imported by `transformers.modeling_layers`,
imported by every model file) and raises:

```
RuntimeError: Detected that PyTorch and TorchAudio were compiled with
different CUDA versions. PyTorch has CUDA version 13.2 whereas TorchAudio
has CUDA version 13.0.
```

**Real fix:** no released `torchaudio` build supports CUDA 13.2 at all
(upstream release lag behind `torch`) — the newest available (`2.11.0`) is
hardcoded to CUDA 13.0 on *every* index, including plain PyPI (which, on
Linux, still ships a CUDA-linked build, not a CPU one). Reinstalling
`torch`/`torchvision`/`torchaudio` together from the same `--index-url`
does **not** fix this — there is nothing to reinstall into that matches.

Since LingBot never uses audio, install a genuinely **CPU-only**
`torchaudio` build instead, from the explicit `cpu` index:

```bash
pip install torchaudio --index-url https://download.pytorch.org/whl/cpu --force-reinstall --no-deps --no-cache-dir
```

A CPU-only build has no CUDA extension, so `torchaudio.ops._torchaudio
.cuda_version()` returns `None` and the mismatch check in
`torchaudio/_extension/utils.py::_check_cuda_version()` never fires. `torch`
itself stays on the CUDA 13.2 build — only `torchaudio` (unused) goes
CPU-only. See `setup_lingbot_v2.sh` step 4 (torch/torchvision from cu132)
+ step 5b (torchaudio from cpu index, separately).

## 3. `tyro` 1.0.16 regression — do not use

`tyro==1.0.16` breaks `flashdreams-run`'s CLI parser construction
(`scripts/cli.py`'s `SuppressFixed`-wrapped single-runner subcommand union)
with:

```
Field runner is marked as Fixed or Suppress but is missing a default value
```

Verified: `flashdreams/flashdreams/scripts/cli.py` is *not* the bug (tested
against the pristine, un-patched version) — this is purely a `tyro`
version regression. `tyro==1.0.15` builds the same parser correctly.

Fix: pin `tyro==1.0.15` (see `setup_lingbot_v2.sh`). Do not "fix" `cli.py`
in response to this error — the code is correct.

## 4. Stale non-editable install shadows the editable one

`pip install -e <pkg>` sometimes leaves (or a prior plain `pip install
<pkg>` leaves) a **static, non-editable copy** of the package physically
inside `.venv/lib/python3.12/site-packages/<pkg>/`, which then silently
shadows the editable/source-pointing install. Symptom: editing source and
re-running produces byte-identical errors no matter what you change,
because Python is loading the stale copy, not your source.

Diagnose:

```bash
python -c "import flashdreams.scripts.cli as c; print(c.__file__)"
```

If this prints a path under `.venv/lib/.../site-packages/flashdreams/...`
instead of your actual source checkout, that's the bug.

Fix: uninstall before reinstalling editable:

```bash
pip uninstall -y flashdreams flashdreams-lingbot
pip install -e "$FLASHDREAMS_ROOT/flashdreams" --no-deps
pip install -e "$HERE" --no-deps
```

`setup_lingbot_v2.sh` step 6 does this automatically now.

## 5. `all_runners()` registry can come back empty

`flashdreams.configs.runner_configs.all_runners()` combines built-in
runners (populated via side-effect imports of each integration's
`config.py`) with plugin-discovered ones (via the
`flashdreams.runner_configs` entry-point group). In this environment it was
observed to return **zero** runners total — not just missing `lingbot`, but
missing every built-in runner too. Root cause not fully identified (see
open question below); `flashdreams-run`'s tyro-based CLI silently falls
back to building a parser over the wrong/empty union in this state, which
is the *actual* proximate cause of the "Field runner is marked as Fixed or
Suppress" error in this environment — not the `tyro` 1.0.16 issue in some
cases, so don't assume #3 is the only cause of that message.

Diagnose:

```bash
python -c "from flashdreams.configs.runner_configs import all_runners; print(len(all_runners()))"
```

**Workaround (current):** bypass the registry and tyro CLI entirely.
`run_direct.py` imports the concrete `RUNNER_LINGBOT_WORLD_FAST` config
object from `lingbot.config` directly and calls
`flashdreams.scripts.cli.main()` with it — the same pattern
`flashdreams/tests/test_launch.py` uses. `run.sh` now calls
`python run_direct.py` instead of `flashdreams-run lingbot-world-fast
webrtc`.

**Open question:** why `all_runners()` / `_SUPPORTED_RUNNERS` is empty has
not been root-caused. `flashdreams/flashdreams/configs/runner_configs.py`'s
own docstring says integrations must be wired in via a side-effect import
line in that file, but no such import lines are present in the current
`ui` branch state. Worth a proper look when there's time to spare, but
`run_direct.py` sidesteps it for now.

## 6. `CLIPImageProcessor` import error (in progress)

Same "transformers masks the real error" pattern as #1, hit transitively
via `flashdreams.recipes.wan.pipeline` → `flashdreams.infra.encoder.image.clip`:

```
ModuleNotFoundError: Could not import module 'CLIPImageProcessor'. Are
this object's requirements defined correctly?
```

Being diagnosed the same way as #1/#2 — import the concrete submodule
directly to find the real underlying exception before assuming it's a
version problem.

## 7. tyro 1.0.16 fix was a false lead; `cli.py` is not the bug

Do not re-patch `flashdreams/flashdreams/scripts/cli.py`'s `runner` field
in response to "Field runner is marked as Fixed or Suppress but is
missing a default value" — that patch attempt was reverted (see git
history around commit `f508ae1b`). Confirmed locally: the *pristine*
`cli.py` builds the tyro parser correctly under `tyro==1.0.15`. If this
error resurfaces, first check whether `all_runners()` is actually empty
(see #8) before touching `cli.py` again.

## 8. `all_runners()` can return an empty registry — use `run_direct.py`

`flashdreams.configs.runner_configs.all_runners()` was observed to
return **zero** runners (not just missing `lingbot` — the built-ins were
missing too), root cause not identified. When that happens,
`flashdreams-run`'s tyro CLI parser ends up built over the wrong/empty
union, which is what actually produces the "Field runner is marked as
Fixed or Suppress" error in this environment — not a `tyro` version
issue in that case.

Diagnose:

```bash
python -c "from flashdreams.configs.runner_configs import all_runners; print(len(all_runners()))"
```

**Workaround in place:** `integrations/lingbot/run_direct.py` bypasses
the registry and tyro entirely — it imports `RUNNER_LINGBOT_WORLD_FAST`
directly from `lingbot.config` and calls
`flashdreams.scripts.cli.main()` with it, the same pattern
`flashdreams/tests/test_launch.py` uses. `run.sh` calls
`python run_direct.py` instead of `flashdreams-run lingbot-world-fast
webrtc`. If `all_runners()` gets root-caused and fixed, `run.sh` could
switch back to the real `flashdreams-run` CLI.

## 9. cam2v was stubbed out, then had to be un-stubbed

`lingbot/controls.py` briefly wrapped `from cam2v.controls import
CameraPoseIntegrator, ...` in a broken try/except stub (no-op
`step()`/`apply()` methods that don't match the real API) to unblock
module imports while the environment was broken. Once the app actually
ran far enough to drive, this crashed with `'CameraPoseIntegrator'
object has no attribute 'integrate_chunk'`. Fixed by installing the
real package instead of stubbing:

```bash
pip install -e ~/flashdreams/apps/cam2v --no-deps
```

`apps/cam2v/defaults.py` also had a bad edit from the same era —
`PresentationMode.ONLY_PRESENT_NEW` (not a real enum member) instead of
the correct `PresentationMode.CONTINUOUS`
(`flashdreams/flashdreams/runtime_v2/session_desc.py` only defines
`ON_DEMAND` and `CONTINUOUS`). **Lesson: don't stub out real
dependencies to work around unrelated environment breakage — fix the
environment, then use the real package.** A stub that "unblocks" an
import silently ships broken functionality until something actually
exercises it.

## 10. Custom prompt: `Unknown event_id='user_prompt'`

The client's free-form custom-prompt field sends
`{event_id: "user_prompt", state, prompt}` over the WebRTC data channel
(`lingbot/webrtc/web/adapter.js`). This event id is deliberately *not*
one of the precomputed catalog entries in `DEFAULT_TEXT_EVENTS`
(portal/storm/fireworks/blue_balloon) — it's a reserved sentinel for a
free-form prompt supplied at request time. Every validation layer in the
pipeline defaulted to catalog-only membership checks and had to be
special-cased for `event_id == "user_prompt"`, and the raw `prompt`
string was getting silently dropped in more than one place before it
ever reached that check. Four fixes, all now required together:

1. `flashdreams/flashdreams/serving/webrtc/manager.py`
   `_handle_event_message` (shared framework layer, used by every
   integration) hardcoded the session-branch payload to
   `{"event_id": ..., "state": ...}`, dropping `prompt` from the raw
   incoming message entirely.
2. `lingbot/webrtc/session.py` `validate_user_event` also stripped
   `prompt` from its returned payload dict, and delegated to
   `_validate_event_request`, which rejects any `event_id` not in the
   precomputed `_event_embeddings` catalog.
3. `lingbot/input_mapping.py` `_text_event_update` — same shape of bug:
   rejected any `event_id` not in `self._text_event_prompts`, and even
   if it hadn't, it would have used the static catalog prompt for that
   id rather than the dynamic one in the payload.
4. `lingbot/demo/providers.py` `_apply_text_event` /
   `_text_event_update` — an exact duplicate of #3 for the
   replay/mp4 demo path (`LingbotInputProvider`), same fix needed.

All four now special-case a reserved `_USER_PROMPT_EVENT_ID = "user_prompt"`
constant (defined locally in each of the three lingbot files — no shared
import, to avoid circular imports between `session.py` and
`input_mapping.py`) to skip the catalog check and read the prompt
straight from the payload.

**The actual embedding/encoding step needed no fix** —
`session.py`'s `_apply_conditioning_update_sync` already correctly
encodes arbitrary prompt text live via `_encode_text_embeddings_sync`
when the prompt string isn't a cache hit against a precomputed catalog
prompt. Only the validation/plumbing layers in front of it were
stripping or rejecting the dynamic prompt before it could get there.

`logger.info()` calls were added at each of the four stages
(`manager.py`, `session.py` x2, `input_mapping.py`) — gated to
state-change points only, not per-frame — so future debugging can see
exactly which stage a prompt reaches in server logs instead of guessing
blind again.

## 11. GPU memory usage looks abnormally high

Observed `GPU mem alloc 110.579 GiB` / `peak 119.327 GiB` for
`lingbot-world-fast`, which is built on a 1.3B parameter base model
(`Wan-AI/Wan2.1-T2V-1.3B-Diffusers`). That's an order of magnitude more
than expected for a model that size. Not yet investigated — flagging so
it isn't mistaken for "expected" if a CUDA OOM shows up again on a
smaller GPU. Possible causes to check first: duplicate model copies
resident (e.g. both a base + reloaded checkpoint), no memory-efficient
attention/offloading enabled by default, or accumulation across
multiple rollout resets in one long-lived process.

## 12. Zombie server processes silently eat the whole GPU AND serve stale code

**Symptom:** code fixes are pushed, pulled, and the server is restarted
repeatedly, but the exact same pre-fix error keeps appearing verbatim,
no matter what changes. Eventually a genuine CUDA OOM shows up with
almost the entire GPU "in use" (e.g. `585760768 bytes free` out of a
`249.81 GiB` card) despite the model itself only needing ~110 GiB.

**Root cause:** a previous `run.sh` process didn't fully exit (e.g. a
`Ctrl+C` landed mid-shutdown, during `gc.collect()` in
`flashdreams/serving/webrtc/bootstrap.py`) and kept running in the
background, still holding its full GPU memory allocation. A *new*
`run.sh` invocation starts a genuinely fresh process with the latest
code, but if the old zombie is still alive, two things go wrong at
once: (a) combined GPU memory from both processes exhausts the card,
and (b) if the browser's WebRTC connection happens to be talking to the
*old* process, every request runs pre-fix code forever, regardless of
how many times the source gets updated and the (different, new)
process gets restarted.

**Diagnose — list every process actually holding GPU memory, not just
what you think is running:**

```bash
nvidia-smi --query-compute-apps=pid,used_memory,process_name --format=csv
for pid in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader); do
  echo "PID $pid owner: $(ps -o user= -p "$pid" 2>/dev/null)"
done
```

More than one `python` process listed here, especially with memory
usage that roughly sums to the full card, is the tell.

**Fix — find which PID (if any) is actually bound to the server port,
kill every other one holding GPU memory, then restart clean:**

```bash
LIVE_PID=$(ss -ltnp 2>/dev/null | grep 8089 | grep -oP 'pid=\K[0-9]+' | head -1)
echo "Live PID on port 8089: ${LIVE_PID:-unknown}"
for pid in $(nvidia-smi --query-compute-apps=pid --format=csv,noheader); do
  if [ "$pid" != "$LIVE_PID" ]; then
    echo "Killing stale PID $pid..."
    kill -9 "$pid"
  fi
done
nvidia-smi --query-compute-apps=pid,used_memory,process_name --format=csv
```

If `nvidia-smi` shows an empty process list afterward, the GPU is
genuinely clean — restart `bash run.sh` and reconnect the browser tab
(a hard refresh doesn't hurt either, to be sure it's not holding an
old WebRTC connection open) before testing anything further.

**Lesson: when a code fix provably doesn't change behavior after
multiple push/pull/restart cycles, stop assuming the code is wrong and
check for a zombie process first.** This one cost most of a debugging
session because every signal pointed at "the fix isn't deployed" when
the fix was deployed correctly the whole time — the browser just
wasn't talking to it.
