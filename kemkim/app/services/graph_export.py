"""Render project coordinates independently of the browser viewport."""

import io
import math
import threading
from typing import Literal

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties
from pydantic import BaseModel, Field, model_validator

_render_lock = threading.Lock()


class GraphExportOptions(BaseModel):
    kind: Literal["dov", "dod"] = "dov"
    format: Literal["png", "svg"] = "png"
    width: float = Field(default=100, ge=2, le=120)
    height: float = Field(default=100, ge=2, le=120)
    font_size: float = Field(default=50, ge=1, le=200)
    dot_size: float = Field(default=20, ge=0, le=500)
    label_size: float = Field(default=12, ge=1, le=100)
    tick_size: float = Field(default=10, ge=1, le=100)
    dpi: int = Field(default=60, ge=30, le=300)
    background: str = Field(default="#ffffff", pattern=r"^#[0-9a-fA-F]{6}$")
    foreground: str = Field(default="#202020", pattern=r"^#[0-9a-fA-F]{6}$")
    words: list[str] | None = Field(default=None, max_length=20000)

    @model_validator(mode="after")
    def limit_pixels(self):
        if self.width * self.height * self.dpi**2 > 36_000_000:
            raise ValueError(
                "이미지는 최대 3,600만 픽셀입니다. 크기나 DPI를 줄여 주세요."
            )
        return self


def render_graph(graph: dict, options: GraphExportOptions) -> bytes:
    section = graph.get(options.kind) or {}
    axis = section.get("axis")
    if not axis or len(axis) != 2 or not all(math.isfinite(float(v)) for v in axis):
        raise ValueError("그래프 기준선이 없습니다.")
    selected = None if options.words is None else set(options.words)
    coords = {
        word: xy
        for word, xy in sorted((section.get("coordinates") or {}).items())
        if word != "axis"
        and (selected is None or word in selected)
        and len(xy) == 2
        and all(math.isfinite(float(v)) for v in xy)
    }
    if not coords:
        raise ValueError("표시할 단어를 하나 이상 선택해 주세요.")
    with _render_lock:
        font = FontProperties(
            fname="/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
            size=options.font_size,
        )
        fig = Figure(
            figsize=(options.width, options.height), facecolor=options.background
        )
        FigureCanvasAgg(fig)
        try:
            ax = fig.add_subplot(111, facecolor=options.background)
            ax.axvline(
                float(axis[0]), color=options.foreground, linestyle="--", linewidth=0.8
            )
            ax.axhline(
                float(axis[1]), color=options.foreground, linestyle="--", linewidth=0.8
            )
            # Match the manager's sorted words, default marker cycle, and labels at coordinates.
            for word, xy in coords.items():
                ax.scatter(float(xy[0]), float(xy[1]), s=options.dot_size)
                ax.text(
                    float(xy[0]),
                    float(xy[1]),
                    word,
                    fontproperties=font,
                    color=options.foreground,
                )
            ax.set_title(
                "Keyword Emergence Map"
                if options.kind == "dov"
                else "Keyword Issue Map",
                fontsize=options.label_size,
                color=options.foreground,
            )
            ax.set_xlabel(
                "Average Term Frequency(TF)"
                if options.kind == "dov"
                else "Average Document Frequency(DF)",
                fontsize=options.label_size,
                color=options.foreground,
            )
            ax.set_ylabel(
                "Time-Weighted increasing rate",
                fontsize=options.label_size,
                color=options.foreground,
            )
            ax.tick_params(labelsize=options.tick_size, colors=options.foreground)
            for spine in ax.spines.values():
                spine.set_color(options.foreground)
            result = io.BytesIO()
            # Fixed canvas dimensions keep the requested resolution predictable.
            fig.savefig(
                result,
                format=options.format,
                dpi=options.dpi,
                facecolor=options.background,
            )
            return result.getvalue()
        finally:
            fig.clear()
