"""Render project coordinates independently of the browser viewport."""

import io
import base64
import math
import threading
from typing import Literal

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties
from pydantic import BaseModel, Field, model_validator
from PIL import Image, ImageDraw, ImageFont

_render_lock = threading.Lock()


class CropRegion(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(ge=0.005, le=1)
    height: float = Field(ge=0.005, le=1)

    @model_validator(mode="after")
    def inside_image(self):
        if self.x + self.width > 1.000001 or self.y + self.height > 1.000001:
            raise ValueError("크롭 영역은 이미지 안에 있어야 합니다.")
        return self


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
    crop: CropRegion | None = None
    include_outside_words: bool = False

    @model_validator(mode="after")
    def limit_pixels(self):
        if self.width * self.height * self.dpi**2 > 36_000_000:
            raise ValueError(
                "이미지는 최대 3,600만 픽셀입니다. 크기나 DPI를 줄여 주세요."
            )
        return self


def _crop_image(data, positions, options):
    """Crop exact original pixels; outside words are legends, never relocated data points."""
    source = Image.open(io.BytesIO(data)).convert("RGB")
    region = options.crop
    left, top = round(region.x * source.width), round(region.y * source.height)
    right = round((region.x + region.width) * source.width)
    bottom = round((region.y + region.height) * source.height)
    left, top = min(left, source.width - 1), min(top, source.height - 1)
    cropped = source.crop(
        (
            left,
            top,
            min(source.width, max(left + 1, right)),
            min(source.height, max(top + 1, bottom)),
        )
    )
    if not options.include_outside_words:
        return cropped
    groups = {side: [] for side in ("left", "right", "top", "bottom")}
    for word, (x, y) in positions.items():
        if (
            region.x <= x <= region.x + region.width
            and region.y <= y <= region.y + region.height
        ):
            continue
        distances = {
            "left": region.x - x,
            "right": x - region.x - region.width,
            "top": region.y - y,
            "bottom": y - region.y - region.height,
        }
        side = max(distances, key=distances.get)
        groups[side].append(word)
    if not any(groups.values()):
        return cropped
    font = ImageFont.truetype(
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        max(10, min(60, round(options.font_size * options.dpi / 72))),
    )
    line_height = sum(font.getmetrics()) + 6
    padding = 20
    measure = ImageDraw.Draw(cropped)

    def wrap(text, width):
        lines, line = [], ""
        for char in text:
            if line and measure.textlength(line + char, font=font) > width:
                lines.append(line)
                line = ""
            line += char
        if line:
            lines.append(line)
        return lines

    side_width = min(700, max(180, round(cropped.width * 0.25)))
    names = {
        "left": "← 왼쪽 영역 밖",
        "right": "오른쪽 영역 밖 →",
        "top": "↑ 위쪽 영역 밖",
        "bottom": "↓ 아래쪽 영역 밖",
    }
    blocks = {}
    for side, words in groups.items():
        if not words:
            continue
        width = side_width if side in ("left", "right") else max(180, cropped.width)
        lines = wrap(f"{names[side]} ({len(words)})", width - padding * 2)
        lines += wrap(" · ".join(words), width - padding * 2)
        blocks[side] = (width, len(lines) * line_height + padding * 2, lines)
    left_width = blocks.get("left", (0, 0, []))[0]
    right_width = blocks.get("right", (0, 0, []))[0]
    top_height = blocks.get("top", (0, 0, []))[1]
    bottom_height = blocks.get("bottom", (0, 0, []))[1]
    middle_width = max(
        cropped.width, blocks.get("top", (0,))[0], blocks.get("bottom", (0,))[0]
    )
    middle_height = max(
        cropped.height, blocks.get("left", (0, 0))[1], blocks.get("right", (0, 0))[1]
    )
    width = left_width + middle_width + right_width
    height = top_height + middle_height + bottom_height
    if width * height > 36_000_000:
        raise ValueError(
            "영역 밖 단어 여백을 포함한 이미지가 너무 큽니다. DPI나 단어 크기를 줄여 주세요."
        )
    result = Image.new("RGB", (width, height), options.background)
    crop_x, crop_y = (
        left_width + (middle_width - cropped.width) // 2,
        top_height + (middle_height - cropped.height) // 2,
    )
    result.paste(cropped, (crop_x, crop_y))
    draw = ImageDraw.Draw(result)
    draw.rectangle(
        (crop_x, crop_y, crop_x + cropped.width - 1, crop_y + cropped.height - 1),
        outline=options.foreground,
        width=1,
    )
    origins = {
        "left": (0, top_height),
        "right": (left_width + middle_width, top_height),
        "top": (left_width, 0),
        "bottom": (left_width, top_height + middle_height),
    }
    for side, (_, _, lines) in blocks.items():
        x, y = origins[side]
        for i, line in enumerate(lines):
            draw.text(
                (x + padding, y + padding + i * line_height),
                line,
                font=font,
                fill=options.foreground,
            )
    return result


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
            figsize=(options.width, options.height),
            facecolor=options.background,
            dpi=options.dpi,
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
                format="png" if options.crop else options.format,
                dpi=options.dpi,
                facecolor=options.background,
            )
            if not options.crop:
                return result.getvalue()
            positions = {}
            for word, xy in coords.items():
                x, y = ax.transData.transform((float(xy[0]), float(xy[1])))
                positions[word] = (x / fig.bbox.width, 1 - y / fig.bbox.height)
            cropped = _crop_image(result.getvalue(), positions, options)
            output = io.BytesIO()
            cropped.save(output, format="PNG")
            if options.format == "png":
                return output.getvalue()
            # The final preview embeds the exact PNG pixels that will be downloaded.
            encoded = base64.b64encode(output.getvalue()).decode("ascii")
            return (
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{cropped.width}" height="{cropped.height}" '
                f'viewBox="0 0 {cropped.width} {cropped.height}"><image width="100%" height="100%" '
                f'href="data:image/png;base64,{encoded}"/></svg>'
            ).encode()
        finally:
            fig.clear()
