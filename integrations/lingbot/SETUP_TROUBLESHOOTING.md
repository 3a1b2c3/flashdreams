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
