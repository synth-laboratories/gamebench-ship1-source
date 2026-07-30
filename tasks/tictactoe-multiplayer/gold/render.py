"""RenderState — visual projection from public state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from gold.state import PublicState


@dataclass
class RenderState:
    profile: str
    ascii_board: str
    cell_labels: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "ascii_board": self.ascii_board,
            "cell_labels": list(self.cell_labels),
        }


def cell_label(cell: str) -> str:
    if not cell:
        return "."
    return cell


def build_render_state(public: PublicState, profile: str = "ascii_tui") -> RenderState:
    labels = [cell_label(cell) for cell in public.board]
    rows = [
        " ".join(labels[0:3]),
        " ".join(labels[3:6]),
        " ".join(labels[6:9]),
    ]
    ascii_board = "\n".join(rows)
    return RenderState(profile=profile, ascii_board=ascii_board, cell_labels=labels)
