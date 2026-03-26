from dataclasses import dataclass

import torch
from torch import Tensor

from flashsim.model.video_dit.base import BaseVideoDiT

class MockRoPEAdapter:
    def __init__(self, t: int, h: int, w: int, dim: int):
        self.t = t
        self.h = h
        self.w = w
        self.dim = dim

    def get_freqs(self, shift_t: int = 0) -> Tensor:
        return torch.randn(self.t * self.h * self.w, 1, 1, self.dim // 2) + shift_t

@dataclass
class MockVideoDiTCondition:
    """
    A mock condition for the video DiT.
    """
    text: Tensor # text embeddings [B, L, D]
    image: Tensor # first frame of the video [B, C, H, W]
    hdmap: Tensor | None = None # hdmap of the video [B, T, C, H, W]

@dataclass
class MockVideoDiTCache:
    """
    A mock cache for the video DiT.
    """
    rope_adapter: MockRoPEAdapter
    autoregressive_index: int = -1


@dataclass
class MockVideoDiTConfig:
    dim: int = 1024
    temporal_patch_size: int = 1
    spatial_patch_size: int = 2
    num_latents_per_chunk: int = 4

class MockVideoDiT(BaseVideoDiT[MockVideoDiTCache]):
    """
    A mock video DiT for testing purposes.
    """
    def __init__(self, config: MockVideoDiTConfig):
        super().__init__()
        self.config = config

    def initialize_cache(
        self, 
        latent_height: int, 
        latent_width: int
    ) -> MockVideoDiTCache:
        return MockVideoDiTCache(
            autoregressive_index=-1,
            rope_adapter=MockRoPEAdapter(
                t=self.config.num_latents_per_chunk, 
                h=latent_height, 
                w=latent_width, 
                dim=self.config.dim
            ),
        )

    def timestep_to_sigma(self, timestep: Tensor) -> Tensor:
        return timestep

    def predict_flow(
        self, 
        noisy_input: Tensor | None, 
        timestep: Tensor, 
        condition: MockVideoDiTCondition, 
        cache: MockVideoDiTCache
    ) -> Tensor:
        shift_t = cache.autoregressive_index * self.config.num_latents_per_chunk
        rope_freqs = cache.rope_adapter.get_freqs(shift_t=shift_t)
        return torch.randn_like(noisy_input)

    @property
    def temporal_patch_size(self) -> int:
        return self.config.temporal_patch_size

    @property
    def spatial_patch_size(self) -> int:
        return self.config.spatial_patch_size