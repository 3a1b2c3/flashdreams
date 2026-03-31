from flashsim.pipeline.alpadreams import AlpadreamsPipelineConfig
from flashsim.model.video_vae.wan import (
    WanVAEInterfaceConfig,
    AVAILABLE_WAN_VAE_CHECKPOINT_PATHS,
)
from flashsim.model.text_encoder.cosmos_reason1 import CosmosReason1TextEncoderConfig
from flashsim.model.video_dit.alpadreams.model import (
    CosmosDiTConfig,
    AVAILABLE_ALPADREAMS_CHECKPOINT_PATHS,
)

ALPADREAMS_CONFIGS = {}

ALPADREAMS_CONFIGS["sv_2steps_chunk2_loc6"] = AlpadreamsPipelineConfig(
    tokenizer=WanVAEInterfaceConfig(
        checkpoint_path=AVAILABLE_WAN_VAE_CHECKPOINT_PATHS["vae"],
    ),
    detokenizer=WanVAEInterfaceConfig(
        checkpoint_path=AVAILABLE_WAN_VAE_CHECKPOINT_PATHS["vae"],
    ),
    text_encoder=CosmosReason1TextEncoderConfig(),
    dit=CosmosDiTConfig(
        enable_hdmap_condition=True,
        encode_with_pixel_shuffle=False,
        enable_cross_view_attn=False,
        # For 720P set to 3.0; for 480P set to 2.0;
        h_extrapolation_ratio=3.0,
        w_extrapolation_ratio=3.0,
        # Difussion schedule
        denoising_timesteps=[1000, 450],
        # Local attn: Number of tokens along T dimension.
        window_size_t=6,
        # Chunk size: Number of tokens along T dimension.
        len_t=2,
        # Checkpoint path
        checkpoint_path=AVAILABLE_ALPADREAMS_CHECKPOINT_PATHS["single_view"][
            "vae_encoding"
        ]["chunk2"],
    ),
)
