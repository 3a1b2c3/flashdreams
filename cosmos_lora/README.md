# Cosmos LoRA Fine-tuning Pipeline

Low-Rank Adaptation (LoRA) fine-tuning for NVIDIA Cosmos video models.

## Directory Structure

```
cosmos_lora/
├── datasets/           # Training data (videos + prompts)
├── configs/            # Training configuration files
├── scripts/            # Python scripts for train/inference
├── checkpoints/        # Saved LoRA checkpoints
├── outputs/            # Generated videos from inference
└── README.md
```

## Setup

### 1. Install Cosmos

```bash
pip install nvidia-cosmos
```

### 2. Prepare Dataset

Place videos in `datasets/videos/`:
- Format: MP4
- Resolution: 720p recommended
- Content: Subject-focused throughout video
- Minimum: 4-10 videos for LoRA

Create prompt files in `datasets/metas/`:
```
videos/video1.mp4 → metas/video1.txt
videos/video2.mp4 → metas/video2.txt
```

Example prompt format:
```
A video of a teal robot moving. High quality, cinematic lighting.
```

### 3. Train LoRA

```bash
python scripts/train_lora.py \
  --data-dir datasets \
  --output-dir checkpoints \
  --epochs 5 \
  --batch-size 1 \
  --lora-rank 32
```

### 4. Run Inference

```bash
python scripts/inference_lora.py \
  --checkpoint checkpoints/latest.pt \
  --prompt "A video of a robot dancing" \
  --output-dir outputs
```

## LoRA Parameters

- `lora_rank`: 16-64 (higher = more capacity, slower)
- `lora_alpha`: Usually equals rank (32 typical)
- `lora_target_modules`: Attention and MLP layers
- `epochs`: 3-10 (5 typical)
- `batch_size`: 1 (VRAM limited)

## Performance Tips

- Use smaller datasets (5-20 videos) for LoRA vs full fine-tune (100+)
- Rank 32 is usually sufficient for style/domain adaptation
- Train for 3-5 epochs before evaluating
- Save checkpoints every epoch for evaluation

## Data Examples

See `datasets/metas/sample_prompts.txt` for examples.

For more info: https://docs.nvidia.com/cosmos
