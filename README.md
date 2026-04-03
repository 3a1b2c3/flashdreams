# Flashsim

## Instructions to run Alpadreams Inference.

```bash
# 1. setup credentials in `credentials/s3_checkpoint.secret` similarly with I4:
# {
#     "aws_access_key_id": "team-sil-videogen",
#     "aws_secret_access_key": <KEY>,
#     "endpoint_url": "https://pdx.s8k.io",
#     "region_name": "us-east-1"
# }

# 2. setup huggingface token and huggingface home to cache
export HF_TOKEN=<YOUR_TOKEN>
export HF_HOME=~/.cache/huggingface

# 3. setup where to cache flashsim checkpoints
export FLASHSIM_CACHE_DIR=~/.cache/flashsim

# 4. Run inference demo.
# Checkpoints and example data are auto-downloaded at first run.
pip install -e .
python scripts/run_alpadreams_inference.py
```
