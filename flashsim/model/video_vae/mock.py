from dataclasses import dataclass

import torch
from torch import Tensor
from flashsim.model.video_vae.base import BaseVideoVAE

@dataclass
class MockVideoVAEEncoderCache:
    """
    A mock cache for the video VAE encoder.
    """
    autoregressive_index: int = -1

@dataclass
class MockVideoVAEDecoderCache:
    """
    A mock cache for the video VAE decoder.
    """
    autoregressive_index: int = -1

@dataclass
class MockVideoVAEConfig:
    input_channel: int = 3
    latent_channel: int = 16
    output_channel: int = 3
    temporal_compression_ratio: int = 4
    spatial_compression_ratio: int = 8

class MockVideoVAE(BaseVideoVAE[MockVideoVAEEncoderCache, MockVideoVAEDecoderCache]):

    def __init__(self, config: MockVideoVAEConfig):
        super().__init__()
        self.config = config

    def initialize_encode_cache(self) -> MockVideoVAEEncoderCache:
        return MockVideoVAEEncoderCache()

    def encode(self, x: Tensor, cache: MockVideoVAEEncoderCache) -> Tensor:
        assert x.ndim == 5, "Expected input tensor to have shape [B, T, C, H, W]"

        B, T, C, H, W = x.shape
        assert T % self.temporal_compression_ratio == 0
        assert H % self.spatial_compression_ratio == 0
        assert W % self.spatial_compression_ratio == 0
        assert C == self.config.input_channel

        Tl = T // self.temporal_compression_ratio
        Hl = H // self.spatial_compression_ratio
        Wl = W // self.spatial_compression_ratio
        Cl = self.config.latent_channel

        z = torch.randn(B, Tl, Cl, Hl, Wl, device=x.device, dtype=x.dtype)
        return z

    def initialize_decode_cache(self) -> MockVideoVAEDecoderCache:
        return MockVideoVAEDecoderCache()

    def decode(self, z: Tensor, cache: MockVideoVAEDecoderCache) -> Tensor:
        assert z.ndim == 5, "Expected input tensor to have shape [B, Tl, Cl, Hl, Wl]"
        B, Tl, Cl, Hl, Wl = z.shape
        assert Cl == self.config.latent_channel

        T = Tl * self.temporal_compression_ratio
        H = Hl * self.spatial_compression_ratio
        W = Wl * self.spatial_compression_ratio
        C = self.config.output_channel

        x = torch.randn(B, T, C, H, W, device=z.device, dtype=z.dtype)
        return x

    @property
    def temporal_compression_ratio(self) -> int:
        return self.config.temporal_compression_ratio

    @property
    def spatial_compression_ratio(self) -> int:
        return self.config.spatial_compression_ratio