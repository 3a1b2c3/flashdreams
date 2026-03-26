from dataclasses import dataclass

import torch
from torch import Tensor

from flashsim.model.text_encoder.base import BaseTextEncoder

@dataclass
class MockTextEncoderConfig:
    dim: int = 1024
    seq_len: int = 256

class MockTextEncoder(BaseTextEncoder):
    """
    A mock text encoder for testing purposes.
    """
    def __init__(self, config: MockTextEncoderConfig):
        super().__init__()
        self.config = config

    def encode(self, text: list[str]) -> Tensor:
        """
        Encode the batch of text into a tensor.

        Args:
            text: The batch of text to encode. [B]

        Returns:
            The encoded tensor. [B, seq_len, dim]
        """
        embeddings = []
        for t in text:
            embeddings.append(torch.randn(self.config.seq_len, self.config.dim))
        return torch.stack(embeddings)