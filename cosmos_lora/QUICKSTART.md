# Cosmos LoRA Quick Start Guide

## 1. Prepare Sample Dataset

```bash
cd cosmos_lora

# Create sample dataset structure
python scripts/prepare_dataset.py --create-sample --data-dir datasets
```

This creates:
- `datasets/videos/` - place your MP4 files here
- `datasets/metas/` - contains sample prompts

## 2. Add Your Videos

Copy your MP4 videos to `datasets/videos/`:
```
datasets/
└── videos/
    ├── video1.mp4
    ├── video2.mp4
    ├── video3.mp4
    └── video4.mp4
```

## 3. Create Prompts

Option A: Auto-generate from template
```bash
python scripts/prepare_dataset.py \
  --data-dir datasets \
  --prompt "A teal robot in an office, cinematic lighting"
```

Option B: Manually edit prompt files
```
datasets/metas/video1.txt: "A robot dancing"
datasets/metas/video2.txt: "A robot walking"
datasets/metas/video3.txt: "A robot reaching for objects"
```

## 4. Validate Dataset

```bash
python scripts/prepare_dataset.py \
  --validate \
  --data-dir datasets
```

Expected output:
```
Found 4 videos
Found 4 prompt files
✓ Dataset is valid
```

## 5. Train LoRA

```bash
python scripts/train_lora.py \
  --data-dir datasets \
  --output-dir checkpoints \
  --lora-rank 32 \
  --epochs 5 \
  --batch-size 1 \
  --learning-rate 1e-4
```

This will:
- Load Cosmos-Predict2.5 Video2World model
- Add LoRA adapters (rank 32 = ~0.2% additional params)
- Train for 5 epochs on your videos
- Save checkpoints after each epoch

## 6. Run Inference

```bash
python scripts/inference_lora.py \
  --checkpoint checkpoints/checkpoint_epoch_5.pt \
  --prompt "A teal robot dancing in a futuristic office" \
  --output-dir outputs \
  --steps 30
```

Generated video: `outputs/generated.mp4`

## Dataset Requirements

**Minimum**: 4-5 videos
**Recommended**: 10-20 videos
**Format**: MP4, 720p
**Content**: Subject should be visible throughout video
**Duration**: 3-10 seconds per video

## LoRA Parameters Explained

| Parameter | Range | Default | Notes |
|-----------|-------|---------|-------|
| `lora_rank` | 8-64 | 32 | Higher = more capacity but slower |
| `lora_alpha` | 8-64 | 32 | Usually equals rank |
| `epochs` | 1-20 | 5 | More epochs = better but risk overfitting |
| `batch_size` | 1 | 1 | VRAM limited |
| `learning_rate` | 1e-5 to 1e-3 | 1e-4 | Small changes matter |

## Troubleshooting

**"Checkpoint not found"**
- Make sure training completed successfully
- Check `checkpoints/` directory contains `.pt` files

**"No prompt files found"**
- Create prompt files in `datasets/metas/`
- One `.txt` file per video (same name as video)

**"Out of memory"**
- Reduce `--batch-size` (already at 1, so try single video)
- Reduce `--lora-rank` to 16
- Reduce `num_inference_steps` to 20

**"Missing cosmos SDK"**
- Install: `pip install nvidia-cosmos`
- Requires CUDA 12.0+

## Next Steps

1. Experiment with different LoRA ranks (16, 32, 64)
2. Try different datasets (style-specific vs. diverse)
3. Adjust learning rate based on convergence
4. Compare outputs from different checkpoint epochs
5. Merge LoRA weights into base model for deployment

## More Info

- Cosmos docs: https://docs.nvidia.com/cosmos
- LoRA paper: https://arxiv.org/abs/2106.09685
- PEFT library: https://github.com/huggingface/peft
