from dataclasses import dataclass, field

import torch
from torch import Tensor

from flashsim.model.video_vae.mock import MockVideoVAEConfig, MockVideoVAE, MockVideoVAEEncoderCache, MockVideoVAEDecoderCache
from flashsim.model.text_encoder.mock import MockTextEncoderConfig, MockTextEncoder
from flashsim.model.video_dit.mock import MockVideoDiTConfig, MockVideoDiT, MockVideoDiTCache, MockVideoDiTCondition


@dataclass
class MockVideoDiffusionPipelineCache:
    tokenizer_cache: MockVideoVAEEncoderCache
    detokenizer_cache: MockVideoVAEDecoderCache
    video_dit_cache: MockVideoDiTCache   
    video_dit_condition: MockVideoDiTCondition # re-usable condition for the video DiT

    latent_height: int
    latent_width: int

    def update(self, autoregressive_index: int, hdmap: Tensor):
        self.tokenizer_cache.autoregressive_index = autoregressive_index
        self.detokenizer_cache.autoregressive_index = autoregressive_index
        self.video_dit_cache.autoregressive_index = autoregressive_index
        self.video_dit_condition.hdmap = hdmap

@dataclass
class MockVideoDiffusionPipelineConfig:
    text_encoder: MockTextEncoderConfig = field(default_factory=MockTextEncoderConfig)
    tokenizer: MockVideoVAEConfig = field(default_factory=MockVideoVAEConfig)
    detokenizer: MockVideoVAEConfig = field(default_factory=MockVideoVAEConfig)
    video_dit: MockVideoDiTConfig = field(default_factory=MockVideoDiTConfig)
    denoising_steps: list[int] = field(default_factory=lambda: [1000, 750, 500, 250])

class MockVideoDiffusionPipeline:
    def __init__(
        self, 
        config: MockVideoDiffusionPipelineConfig, 
        dtype: torch.dtype = torch.bfloat16, 
        device: torch.device = torch.device("cuda")
    ):
        self.config = config
        self.dtype = dtype
        self.device = device
        self.text_encoder = MockTextEncoder(config.text_encoder)
        self.tokenizer = MockVideoVAE(config.tokenizer)
        self.video_dit = MockVideoDiT(config.video_dit)
        self.detokenizer = MockVideoVAE(config.detokenizer)

    def initialize_cache(
        self, 
        text: str,
        image: Tensor,
        video_height: int, 
        video_width: int
    ):
        latent_height = video_height // self.spatial_compression_ratio
        latent_width = video_width // self.spatial_compression_ratio
        return MockVideoDiffusionPipelineCache(
            tokenizer_cache=self.tokenizer.initialize_encode_cache(),
            video_dit_cache=self.video_dit.initialize_cache(latent_height=latent_height, latent_width=latent_width),
            detokenizer_cache=self.detokenizer.initialize_decode_cache(),
            video_dit_condition=MockVideoDiTCondition(
                text=self.text_encoder.encode(text),
                image=image,
            ),
            latent_height=latent_height,
            latent_width=latent_width,
        )

    def streaming_inference(self, autoregressive_index: int, hdmap: Tensor, cache: MockVideoDiffusionPipelineCache):
        # 1. encode the hdmap
        encoded_hdmap = self.tokenizer.encode(hdmap, cache=cache.tokenizer_cache)

        # patchify

        # 2. run DiT denoising
        batch_size = hdmap.shape[0]
        cache.update(autoregressive_index=autoregressive_index, hdmap=encoded_hdmap)      
        clean_input = None
        for denoising_step in self.config.denoising_steps:
            timestep = torch.full(
                (batch_size,), 
                fill_value=denoising_step, 
                device=self.device, 
                dtype=self.dtype
            )
            if clean_input is None:
                noisy_input = torch.randn(
                    (batch_size, cache.latent_height, cache.latent_width, self.config.video_dit.dim),
                    device=self.device,
                    dtype=self.dtype
                )
            else:
                noisy_input = self.video_dit.add_noise(
                    clean_input=clean_input,
                    timestep=timestep,
                )

            predicted_flow = self.video_dit.predict_flow(
                noisy_input=noisy_input, 
                timestep=timestep, 
                condition=cache.video_dit_condition, 
                cache=cache.video_dit_cache
            )
            clean_input = self.video_dit.denoise(
                noisy_input=noisy_input,
                timestep=timestep,
                predicted_flow=predicted_flow
            )

        # unpatchify

        # 3. decode the clean input
        clean_input = self.detokenizer.decode(clean_input, cache=cache.detokenizer_cache)
        return clean_input

    @property
    def temporal_compression_ratio(self) -> int:
        return  self.tokenizer.temporal_compression_ratio * self.video_dit.temporal_patch_size

    @property
    def spatial_compression_ratio(self) -> int:
        return self.tokenizer.spatial_compression_ratio * self.video_dit.spatial_patch_size

if __name__ == "__main__":
    config = MockVideoDiffusionPipelineConfig()
    pipeline = MockVideoDiffusionPipeline(config)
    cache = pipeline.initialize_cache(text="Hello, world!", image=torch.randn(1, 3, 256, 256), video_height=256, video_width=256)
    clean_input = pipeline.streaming_inference(autoregressive_index=0, hdmap=torch.randn(1, 100, 3, 256, 256), cache=cache)
    print(clean_input.shape)