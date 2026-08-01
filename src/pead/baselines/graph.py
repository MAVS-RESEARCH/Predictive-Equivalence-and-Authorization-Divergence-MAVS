"""Registered relational graph neural-network architecture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

GRAPH_GRID = tuple(
    {"learning_rate": lr, "weight_decay": wd, "hidden_dimension": hidden}
    for lr in (1e-4, 3e-4)
    for wd in (1e-5, 1e-4)
    for hidden in (128, 256)
)
GRAPH_SCHEDULE = {
    "batch_size": 64,
    "max_epochs": 80,
    "patience": 10,
    "seeds": (101, 211, 307),
    "truncation": "none",
}


@dataclass(frozen=True)
class GraphContract:
    layers: int = 4
    hidden_dimension: int = 256
    relation_embedding_dimension: int = 64
    residual: bool = True
    normalization: str = "LayerNorm"
    activation: str = "ReLU"
    dropout: float = 0.10
    pooling: str = "attention_global"
    context_head: str = "two_layer_mlp_three_class"


def build_relational_gnn(node_dimension: int, relation_types: int, *, hidden_dimension: int = 256) -> Any:
    """Build a four-layer relation-conditioned residual message network."""

    import torch
    import torch.nn as nn

    class RelationalLayer(nn.Module):
        def __init__(self, dimension: int) -> None:
            super().__init__()
            self.message = nn.Linear(dimension + 64, dimension)
            self.norm = nn.LayerNorm(dimension)
            self.dropout = nn.Dropout(0.10)

        def forward(self, nodes: Any, relation_context: Any) -> Any:
            update = torch.relu(self.message(torch.cat((nodes, relation_context), dim=-1)))
            return self.norm(nodes + self.dropout(update))

    class RelationalGraphNetwork(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.input = nn.Linear(node_dimension, hidden_dimension)
            self.relations = nn.Embedding(relation_types, 64)
            self.layers = nn.ModuleList(RelationalLayer(hidden_dimension) for _ in range(4))
            self.attention = nn.Linear(hidden_dimension, 1)
            self.context = nn.Sequential(
                nn.Linear(hidden_dimension, hidden_dimension),
                nn.ReLU(),
                nn.Linear(hidden_dimension, 3),
            )

        def forward(self, node_features: Any, relation_ids: Any) -> Any:
            nodes = self.input(node_features)
            relation_context = self.relations(relation_ids)
            for layer in self.layers:
                nodes = layer(nodes, relation_context)
            weights = torch.softmax(self.attention(nodes), dim=-2)
            return self.context((weights * nodes).sum(dim=-2))

    return RelationalGraphNetwork()
