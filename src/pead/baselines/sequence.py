"""Registered canonical-record Transformer and deterministic text contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

TRANSFORMER_GRID = tuple(
    {"learning_rate": lr, "weight_decay": wd, "warmup_fraction": warmup}
    for lr in (1e-4, 3e-4)
    for wd in (0.01, 0.1)
    for warmup in (0.05, 0.10)
)
TRANSFORMER_SCHEDULE = {
    "batch_size": 128,
    "max_epochs": 60,
    "patience": 8,
    "gradient_clip": 1.0,
    "seeds": (101, 211, 307),
}


@dataclass(frozen=True)
class SequencePreprocessingContract:
    vocabulary_size: int = 32_768
    vocabulary_fit_partition: str = "development_fit"
    normalization: str = "NFC"
    numeric_handling: str = "development_fit_numeric_buckets"
    unknown_token: str = "[UNK]"
    maximum_tokens: int = 512
    truncation: str = "deterministic_head_plus_tail_with_manifest"


def deterministic_head_tail(tokens: tuple[int, ...], maximum: int = 512) -> tuple[tuple[int, ...], dict[str, int | bool]]:
    if len(tokens) <= maximum:
        return tokens, {"truncated": False, "head": len(tokens), "tail": 0}
    head = maximum // 2
    tail = maximum - head
    return tokens[:head] + tokens[-tail:], {"truncated": True, "head": head, "tail": tail}


def build_transformer(vocabulary_size: int = 32_768) -> Any:
    """Build 4-layer d256/h8/ff1024/dropout.10 CLS three-class encoder."""

    import torch
    import torch.nn as nn

    class CanonicalRecordTransformer(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.embedding = nn.Embedding(vocabulary_size, 256)
            layer = nn.TransformerEncoderLayer(
                d_model=256,
                nhead=8,
                dim_feedforward=1024,
                dropout=0.10,
                batch_first=True,
                norm_first=True,
            )
            self.encoder = nn.TransformerEncoder(layer, num_layers=4)
            self.classifier = nn.Linear(256, 3)

        def forward(self, token_ids: Any) -> Any:
            encoded = self.encoder(self.embedding(token_ids))
            return self.classifier(encoded[:, 0, :])

    return CanonicalRecordTransformer()
