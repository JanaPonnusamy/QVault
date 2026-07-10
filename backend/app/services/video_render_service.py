"""Deterministic frame renderer for generated quiz videos.

Consumes a :class:`VideoTimeline` plus a JSON template (``assets/templates``)
and streams raw RGB frames straight into ffmpeg's stdin — no frame list, no
in-memory video. One shared timeline drives both orientations; the
:class:`Layout` class is the only place landscape and portrait differ.

Visual language: animated multi-blob gradient background with floating
particles (never a static screen), glassmorphism cards (blurred backdrop +
translucent fill + light border + soft shadow), eased slide/fade/pop/pulse
animations, a per-question progress bar, an animated 3-2-1 countdown, a green
glow + check reveal on the correct option with the others dimmed, and a
word-highlight subtitle bar synchronized to the narration.
"""

from __future__ import annotations

import json
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.config.settings import settings
from app.services.video_script_service import OPTION_LETTERS
from app.services.video_timeline_service import SceneTimeline, VideoTimeline
from app.shared.logging import get_logger

logger = get_logger("video_render")

FADE = 0.45  # default in-animation length (seconds)


# --------------------------------------------------------------------------- easing
def clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def ease_out_cubic(x: float) -> float:
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def ease_out_back(x: float) -> float:
    x = clamp01(x)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


# --------------------------------------------------------------------------- templates
def list_templates() -> list[dict]:
    templates = []
    for path in sorted(settings.templates_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            templates.append(
                {
                    "key": data.get("key", path.stem),
                    "name": data.get("name", path.stem.title()),
                    "description": data.get("description", ""),
                }
            )
        except (OSError, json.JSONDecodeError):
            logger.warning("Skipping unreadable template %s", path.name)
    return templates


def load_template(key: str) -> dict:
    path = settings.templates_dir / f"{key}.json"
    if not path.exists():
        raise FileNotFoundError(f"Template '{key}' not found under assets/templates")
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- layout
@dataclass
class Layout:
    """All geometry for one orientation. The timeline itself never changes."""

    width: int
    height: int
    margin: int
    header_y: int
    counter_y: int
    progress_y: int
    progress_w: int
    question_y: int
    question_h: int
    options_y: int
    option_h: int
    option_gap: int
    think_cy: int
    answer_y: int
    answer_h: int
    explanation_y: int
    explanation_h: int
    subtitle_y: int
    f_header: int
    f_counter: int
    f_question: int
    f_option: int
    f_card_label: int
    f_card_value: int
    f_explanation: int
    f_subtitle: int
    f_countdown: int
    f_title: int

    @property
    def content_w(self) -> int:
        return self.width - 2 * self.margin

    @property
    def option_w(self) -> int:
        return (self.content_w - self.option_gap) // 2

    def option_pos(self, index: int, count: int) -> tuple[int, int]:
        """Two options per row; a lone option in the last row is centered."""
        row, col = divmod(index, 2)
        y = self.options_y + row * (self.option_h + self.option_gap)
        if index == count - 1 and count % 2 == 1:
            return (self.width - self.option_w) // 2, y
        return self.margin + col * (self.option_w + self.option_gap), y

    @staticmethod
    def landscape() -> "Layout":
        return Layout(
            width=1920, height=1080, margin=210,
            header_y=44, counter_y=104, progress_y=158, progress_w=560,
            question_y=200, question_h=240,
            options_y=496, option_h=108, option_gap=36,
            think_cy=772,
            answer_y=806, answer_h=88,
            explanation_y=908, explanation_h=118,
            subtitle_y=1036,
            f_header=30, f_counter=26, f_question=42, f_option=28,
            f_card_label=20, f_card_value=32, f_explanation=24, f_subtitle=26,
            f_countdown=64, f_title=72,
        )

    @staticmethod
    def portrait() -> "Layout":
        return Layout(
            width=1080, height=1920, margin=70,
            header_y=150, counter_y=224, progress_y=286, progress_w=520,
            question_y=352, question_h=390,
            options_y=800, option_h=148, option_gap=38,
            think_cy=1218,
            answer_y=1272, answer_h=112,
            explanation_y=1420, explanation_h=250,
            subtitle_y=1750,
            f_header=34, f_counter=28, f_question=46, f_option=30,
            f_card_label=22, f_card_value=38, f_explanation=28, f_subtitle=30,
            f_countdown=88, f_title=84,
        )


# --------------------------------------------------------------------------- text utils
_FONT_CACHE: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def font(template: dict, weight: str, size: int) -> ImageFont.FreeTypeFont:
    name = template["fonts"][weight]
    key = (name, size)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ImageFont.truetype(str(settings.fonts_dir / name), size)
    return _FONT_CACHE[key]


def wrap_text(draw: ImageDraw.ImageDraw, text: str, fnt, max_width: int) -> list[str]:
    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=fnt) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def fit_wrapped(
    template: dict, weight: str, text: str, box_w: int, box_h: int, size: int, min_size: int = 16
) -> tuple[ImageFont.FreeTypeFont, list[str], int]:
    """Shrink the font until the wrapped text fits the box; returns font/lines/line height."""
    probe = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    while True:
        fnt = font(template, weight, size)
        lines = wrap_text(probe, text, fnt, box_w)
        line_h = int(size * 1.38)
        if line_h * len(lines) <= box_h or size <= min_size:
            return fnt, lines, line_h
        size -= 2


# --------------------------------------------------------------------------- background
class BackgroundRenderer:
    """Animated gradient blobs + drifting particles, computed at low res."""

    def __init__(self, width: int, height: int, template: dict) -> None:
        self.width, self.height = width, height
        cfg = template["background"]
        self.base = np.array(cfg["base"], dtype=np.float32)
        self.blobs = cfg["blobs"]
        self.vignette_strength = float(cfg.get("vignette", 0.3))
        self.lw, self.lh = max(width // 12, 96), max(height // 12, 96)
        ys, xs = np.mgrid[0 : self.lh, 0 : self.lw].astype(np.float32)
        self.nx, self.ny = xs / self.lw, ys / self.lh
        cx, cy = self.nx - 0.5, (self.ny - 0.5) * (height / width)
        radial = np.sqrt(cx * cx + cy * cy)
        self.vignette = 1.0 - self.vignette_strength * clamp_array(radial * 1.6 - 0.25)

        pcfg = cfg.get("particles", {})
        rng = np.random.default_rng(42)
        self.p_count = int(pcfg.get("count", 0))
        self.p_color = tuple(pcfg.get("color", [255, 255, 255]))
        self.p_alpha = int(pcfg.get("alpha", 40))
        self.p_speed = float(pcfg.get("speed", 12))
        self.p_x = rng.uniform(0, width, self.p_count)
        self.p_y = rng.uniform(0, height, self.p_count)
        self.p_r = rng.uniform(pcfg.get("min_r", 2), pcfg.get("max_r", 5), self.p_count)
        self.p_phase = rng.uniform(0, math.tau, self.p_count)
        self.p_speed_mul = rng.uniform(0.6, 1.4, self.p_count)

    def frame(self, t: float) -> tuple[Image.Image, Image.Image, Image.Image | None]:
        """Returns (full-res background, low-res blurred backdrop, particle overlay).

        The blurred backdrop stays at low resolution; the compositor upscales
        only the card-sized regions it actually needs. Particles come back as a
        separate RGBA overlay so the caller composites them onto its already-RGBA
        canvas instead of paying two extra full-frame mode conversions here.
        """
        acc = np.ones((self.lh, self.lw, 1), dtype=np.float32) * self.base
        for i, blob in enumerate(self.blobs):
            drift, speed = blob["drift"], blob["speed"]
            phase = i * 2.1
            bx = blob["cx"] + drift * math.sin(math.tau * speed * t + phase)
            by = blob["cy"] + drift * math.cos(math.tau * speed * t * 0.83 + phase * 1.7)
            dx, dy = self.nx - bx, (self.ny - by) * (self.lh / self.lw) * (self.width / self.height)
            fall = np.exp(-(dx * dx + dy * dy) / (2 * (blob["radius"] * 0.42) ** 2))
            acc += fall[..., None] * np.array(blob["color"], dtype=np.float32) * 0.62
        acc *= self.vignette[..., None]
        low = Image.fromarray(np.clip(acc, 0, 255).astype(np.uint8), "RGB")
        bg = low.resize((self.width, self.height), Image.BILINEAR)
        blurred_low = low.filter(ImageFilter.GaussianBlur(3))

        particles = None
        if self.p_count:
            particles = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(particles)
            for i in range(self.p_count):
                y = (self.p_y[i] - self.p_speed * self.p_speed_mul[i] * t) % (self.height + 60) - 30
                x = self.p_x[i] + 26 * math.sin(0.25 * t + self.p_phase[i])
                r = self.p_r[i]
                tw = 0.5 + 0.5 * math.sin(0.8 * t + self.p_phase[i] * 2)
                a = int(self.p_alpha * (0.4 + 0.6 * tw))
                draw.ellipse((x - r, y - r, x + r, y + r), fill=(*self.p_color, a))
        return bg, blurred_low, particles


def clamp_array(a: np.ndarray) -> np.ndarray:
    return np.clip(a, 0.0, 1.0)


# --------------------------------------------------------------------------- glass cards
def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius, fill=255)
    return mask


PAD = 42  # shadow/glow padding baked around every card


@dataclass
class Card:
    """Pre-rendered glass card: overlay (fill/border/content), shadow and mask."""

    overlay: Image.Image  # padded RGBA
    shadow: Image.Image  # padded RGBA
    mask: Image.Image  # unpadded L mask for the glass backdrop
    w: int
    h: int


def make_card(
    template: dict,
    w: int,
    h: int,
    strong: bool = False,
    border: tuple | None = None,
) -> Card:
    glass = template["glass"]
    radius = min(glass["radius"], h // 2)
    fill = tuple(glass["fill_strong" if strong else "fill"])
    border = border or tuple(glass["border"])

    overlay = Image.new("RGBA", (w + 2 * PAD, h + 2 * PAD), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    box = (PAD, PAD, PAD + w - 1, PAD + h - 1)
    draw.rounded_rectangle(box, radius, fill=fill)
    draw.rounded_rectangle(box, radius, outline=border, width=2)
    # subtle top light edge for the glass feel
    edge = Image.new("RGBA", overlay.size, (0, 0, 0, 0))
    ImageDraw.Draw(edge).rounded_rectangle(
        (PAD + 2, PAD + 2, PAD + w - 3, PAD + h // 2), radius, fill=(255, 255, 255, 14)
    )
    overlay.alpha_composite(edge)

    shadow = Image.new("RGBA", overlay.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (PAD, PAD + 8, PAD + w - 1, PAD + h + 7), radius, fill=(0, 0, 0, glass["shadow_alpha"])
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(12))

    return Card(overlay=overlay, shadow=shadow, mask=rounded_mask((w, h), radius), w=w, h=h)


def make_glow(template: dict, w: int, h: int, color: tuple) -> Image.Image:
    radius = min(template["glass"]["radius"], h // 2)
    glow = Image.new("RGBA", (w + 2 * PAD, h + 2 * PAD), (0, 0, 0, 0))
    ImageDraw.Draw(glow).rounded_rectangle(
        (PAD - 6, PAD - 6, PAD + w + 5, PAD + h + 5), radius + 6, fill=(*color, 150)
    )
    return glow.filter(ImageFilter.GaussianBlur(16))


def draw_check_icon(size: int, color: tuple) -> Image.Image:
    icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(icon)
    draw.ellipse((0, 0, size - 1, size - 1), fill=(*color, 255))
    s = size / 32.0
    draw.line(
        [(9 * s, 16.5 * s), (14 * s, 21.5 * s), (23.5 * s, 10.5 * s)],
        fill=(255, 255, 255, 255),
        width=max(2, int(3.2 * s)),
        joint="curve",
    )
    return icon


def draw_bulb_icon(size: int, color: tuple) -> Image.Image:
    icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(icon)
    s = size / 32.0
    draw.ellipse((8 * s, 3 * s, 24 * s, 19 * s), outline=(*color, 255), width=max(2, int(2.4 * s)))
    draw.line([(13 * s, 22 * s), (19 * s, 22 * s)], fill=(*color, 255), width=max(2, int(2.2 * s)))
    draw.line([(14 * s, 26 * s), (18 * s, 26 * s)], fill=(*color, 255), width=max(2, int(2.2 * s)))
    return icon


# --------------------------------------------------------------------------- scene sprites
class SceneSprites:
    """Per-question pre-rendered layers; built lazily, dropped when the scene ends."""

    def __init__(self, template: dict, layout: Layout, scene: SceneTimeline) -> None:
        self.template = template
        self.layout = layout
        self.scene = scene
        colors = template["colors"]
        L = layout
        q = scene.question

        # question card
        self.question_card = make_card(template, L.content_w, L.question_h, strong=True)
        self._draw_centered_text(
            self.question_card.overlay, q.question, "semibold", L.f_question,
            L.content_w - 90, L.question_h - 44, tuple(colors["text"]),
        )

        # option cards + reveal layers
        self.option_cards: list[Card] = []
        letter_bg = tuple(colors["option_letter_bg"])
        for i, option in enumerate(q.options):
            card = make_card(template, L.option_w, L.option_h)
            self._draw_option(card.overlay, OPTION_LETTERS[i], option, letter_bg)
            self.option_cards.append(card)
        correct = tuple(colors["correct"])
        self.correct_glow = make_glow(template, L.option_w, L.option_h, correct)
        self.correct_border = Image.new(
            "RGBA", (L.option_w + 2 * PAD, L.option_h + 2 * PAD), (0, 0, 0, 0)
        )
        ImageDraw.Draw(self.correct_border).rounded_rectangle(
            (PAD, PAD, PAD + L.option_w - 1, PAD + L.option_h - 1),
            min(template["glass"]["radius"], L.option_h // 2),
            outline=(*correct, 255),
            width=4,
        )
        self.check_icon = draw_check_icon(int(L.option_h * 0.42), correct)

        # answer card
        self.answer_card = make_card(template, self._answer_w(), L.answer_h, strong=True,
                                     border=(*correct, 160))
        self._draw_answer(self.answer_card.overlay, q.answer_text)

        # explanation card
        self.explanation_card = None
        if scene.explanation_text:
            self.explanation_card = make_card(template, L.content_w, L.explanation_h)
            self._draw_explanation(self.explanation_card.overlay, scene.explanation_text)

    def _answer_w(self) -> int:
        return min(self.layout.content_w, max(560, int(self.layout.content_w * 0.55)))

    def _draw_centered_text(self, overlay, text, weight, size, box_w, box_h, color) -> None:
        draw = ImageDraw.Draw(overlay)
        fnt, lines, line_h = fit_wrapped(self.template, weight, text, box_w, box_h, size)
        total_h = line_h * len(lines)
        y = PAD + (overlay.height - 2 * PAD - total_h) // 2 + (line_h - fnt.size) // 2
        for line in lines:
            x = PAD + (overlay.width - 2 * PAD - draw.textlength(line, font=fnt)) // 2
            draw.text((x, y), line, font=fnt, fill=(*color, 255))
            y += line_h

    def _draw_option(self, overlay, letter, text, letter_bg) -> None:
        L, colors = self.layout, self.template["colors"]
        draw = ImageDraw.Draw(overlay)
        chip = int(L.option_h * 0.52)
        cx, cy = PAD + 26, PAD + (L.option_h - chip) // 2
        draw.ellipse((cx, cy, cx + chip, cy + chip), fill=letter_bg)
        letter_font = font(self.template, "bold", int(chip * 0.55))
        lw = draw.textlength(letter, font=letter_font)
        draw.text(
            (cx + (chip - lw) / 2, cy + chip * 0.16), letter,
            font=letter_font, fill=(255, 255, 255, 255),
        )
        text_x = cx + chip + 22
        box_w = L.option_w - (text_x - PAD) - 30
        fnt, lines, line_h = fit_wrapped(
            self.template, "medium", text, box_w, L.option_h - 24, L.f_option
        )
        total_h = line_h * len(lines)
        y = PAD + (L.option_h - total_h) // 2 + (line_h - fnt.size) // 2
        for line in lines:
            draw.text((text_x, y), line, font=fnt, fill=(*colors["text"], 255))
            y += line_h

    def _draw_answer(self, overlay, answer) -> None:
        L, colors = self.layout, self.template["colors"]
        draw = ImageDraw.Draw(overlay)
        correct = tuple(colors["correct"])
        w = self._answer_w()
        icon = draw_check_icon(int(L.f_card_label * 1.2), correct)
        label_font = font(self.template, "semibold", L.f_card_label)
        label = "CORRECT ANSWER"
        label_w = draw.textlength(label, font=label_font)
        lx = PAD + (w - (icon.width + 10 + label_w)) // 2
        ly = PAD + 14
        overlay.alpha_composite(icon, (int(lx), int(ly)))
        draw.text((lx + icon.width + 10, ly), label, font=label_font, fill=(*correct, 255))
        value_font, lines, _ = fit_wrapped(
            self.template, "bold", answer, w - 80, L.answer_h - 40 - label_font.size, L.f_card_value
        )
        vy = ly + label_font.size + 10
        for line in lines:
            vx = PAD + (w - draw.textlength(line, font=value_font)) // 2
            draw.text((vx, vy), line, font=value_font, fill=(*colors["text"], 255))
            vy += int(value_font.size * 1.3)

    def _draw_explanation(self, overlay, text) -> None:
        L, colors = self.layout, self.template["colors"]
        draw = ImageDraw.Draw(overlay)
        accent = tuple(colors["accent2"])
        icon = draw_bulb_icon(int(L.f_card_label * 1.25), accent)
        label_font = font(self.template, "semibold", L.f_card_label)
        overlay.alpha_composite(icon, (PAD + 26, PAD + 14))
        draw.text(
            (PAD + 26 + icon.width + 10, PAD + 14), "EXPLANATION",
            font=label_font, fill=(*accent, 255),
        )
        body_top = PAD + 14 + label_font.size + 10
        fnt, lines, line_h = fit_wrapped(
            self.template, "regular", text, L.content_w - 100,
            L.explanation_h - (body_top - PAD) - 16, L.f_explanation,
        )
        y = body_top
        for line in lines:
            draw.text((PAD + 30, y), line, font=fnt, fill=(*colors["muted"], 255))
            y += line_h


# --------------------------------------------------------------------------- renderer
class VideoRenderService:
    """Streams composed frames into ffmpeg; one instance per rendered video."""

    def __init__(
        self,
        timeline: VideoTimeline,
        template: dict,
        orientation: str,
        fps: int | None = None,
    ) -> None:
        self.timeline = timeline
        self.template = template
        self.layout = Layout.portrait() if orientation == "portrait" else Layout.landscape()
        self.fps = fps or settings.video_fps
        self.background = BackgroundRenderer(self.layout.width, self.layout.height, template)
        self._sprites: dict[int, SceneSprites] = {}
        self._caption_cache: tuple | None = None
        self._caption_image: Image.Image | None = None
        self._header_image: Image.Image | None = None
        self._scene_ptr = 0
        self._caption_ptr = 0

    # ---------------- public
    def render(
        self,
        audio_path: Path,
        out_path: Path,
        thumbnail_path: Path | None = None,
        progress=None,
    ) -> Path:
        L = self.layout
        total_frames = int(self.timeline.duration * self.fps)
        thumb_frame = self._thumbnail_frame()
        cmd = [
            settings.ffmpeg_path, "-y", "-v", "error",
            "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", f"{L.width}x{L.height}", "-r", str(self.fps), "-i", "pipe:0",
            "-i", str(audio_path),
            "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-movflags", "+faststart",
            str(out_path),
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            for i in range(total_frames):
                frame = self.compose_frame(i / self.fps)
                proc.stdin.write(frame.tobytes())
                if thumbnail_path and i == thumb_frame:
                    frame.save(thumbnail_path)
                if progress and i % (max(total_frames // 50, 1)) == 0:
                    progress(int(50 + 48 * i / total_frames), "Rendering frames")
            proc.stdin.close()
            if proc.wait(timeout=300) != 0:
                raise RuntimeError(f"ffmpeg encode failed: {proc.stderr.read().decode(errors='replace')[:500]}")
        finally:
            if proc.poll() is None:
                proc.kill()
        return out_path

    def _thumbnail_frame(self) -> int:
        if self.timeline.scenes:
            return int((self.timeline.scenes[0].reveal_at + 0.6) * self.fps)
        return int(self.fps)

    # ---------------- frame composition
    def compose_frame(self, t: float) -> Image.Image:
        bg, blurred, particles = self.background.frame(t)
        canvas = bg.convert("RGBA")
        if particles is not None:
            canvas.alpha_composite(particles)
        self._blurred = blurred

        tl = self.timeline
        if t < tl.intro_end:
            self._draw_title_card(canvas, t, intro=True)
        elif t >= tl.outro_in:
            self._draw_title_card(canvas, t, intro=False)
        else:
            scene = self._active_scene(t)
            if scene is not None:
                self._draw_header(canvas, t, scene)
                self._draw_scene(canvas, t, scene)
        self._draw_captions(canvas, t)
        return canvas.convert("RGB")

    def _active_scene(self, t: float) -> SceneTimeline | None:
        scenes = self.timeline.scenes
        while self._scene_ptr < len(scenes) - 1 and t >= scenes[self._scene_ptr].end:
            self._sprites.pop(scenes[self._scene_ptr].index, None)  # free finished scene
            self._scene_ptr += 1
        scene = scenes[self._scene_ptr]
        return scene if scene.question_in <= t < scene.end else (
            scene if t >= scene.question_in else None
        )

    def _scene_sprites(self, scene: SceneTimeline) -> SceneSprites:
        sprites = self._sprites.get(scene.index)
        if sprites is None:
            sprites = self._sprites[scene.index] = SceneSprites(self.template, self.layout, scene)
        return sprites

    # ---------------- compositing helpers
    def _paste_glass(
        self,
        canvas: Image.Image,
        card: Card,
        x: int,
        y: int,
        alpha: float,
        dy: float = 0.0,
        scale: float = 1.0,
        extra_under: tuple[Image.Image, float] | None = None,
        extra_over: list[tuple[Image.Image, float]] | None = None,
    ) -> None:
        if alpha <= 0.01:
            return
        a = int(255 * clamp01(alpha))
        px, py = int(x), int(y + dy)

        overlay, shadow, mask = card.overlay, card.shadow, card.mask
        w, h = card.w, card.h
        if scale != 1.0:
            sw, sh = max(2, int(overlay.width * scale)), max(2, int(overlay.height * scale))
            overlay = overlay.resize((sw, sh), Image.BILINEAR)
            shadow = shadow.resize((sw, sh), Image.BILINEAR)
            mask = mask.resize((max(2, int(w * scale)), max(2, int(h * scale))), Image.BILINEAR)
            px += (card.overlay.width - sw) // 2
            py += (card.overlay.height - sh) // 2
            w, h = mask.size

        def faded(img: Image.Image, factor: float = 1.0) -> Image.Image:
            f = int(a * factor)
            if f >= 255:
                return img
            fade_img = img.copy()
            fade_img.putalpha(fade_img.getchannel("A").point(lambda v: v * f // 255))
            return fade_img

        canvas.alpha_composite(faded(shadow), (px, py))
        if extra_under is not None:
            eu, factor = extra_under
            if eu.size != overlay.size:
                eu = eu.resize(overlay.size, Image.BILINEAR)
            canvas.alpha_composite(faded(eu, factor), (px, py))
        # glass backdrop: blurred background clipped to the card shape,
        # upscaled from the low-res blur only for this card's region
        gx, gy = px + (overlay.width - w) // 2, py + (overlay.height - h) // 2
        crop_box = (
            max(gx, 0), max(gy, 0),
            min(gx + w, canvas.width), min(gy + h, canvas.height),
        )
        if crop_box[2] > crop_box[0] and crop_box[3] > crop_box[1]:
            rx = self._blurred.width / canvas.width
            ry = self._blurred.height / canvas.height
            region = self._blurred.crop(
                (
                    int(crop_box[0] * rx), int(crop_box[1] * ry),
                    max(int(crop_box[2] * rx), int(crop_box[0] * rx) + 1),
                    max(int(crop_box[3] * ry), int(crop_box[1] * ry) + 1),
                )
            ).resize((crop_box[2] - crop_box[0], crop_box[3] - crop_box[1]), Image.BILINEAR)
            m = mask.crop(
                (crop_box[0] - gx, crop_box[1] - gy, crop_box[2] - gx, crop_box[3] - gy)
            )
            if a < 255:
                m = m.point(lambda v: v * a // 255)
            canvas.paste(region, (crop_box[0], crop_box[1]), m)
        canvas.alpha_composite(faded(overlay), (px, py))
        for extra, factor in extra_over or []:
            eo = extra
            if eo.size != overlay.size:
                eo = eo.resize(overlay.size, Image.BILINEAR)
            canvas.alpha_composite(faded(eo, factor), (px, py))

    def _float_dy(self, t: float, seed: float, amp: float = 3.0) -> float:
        return amp * math.sin(0.9 * t + seed * 1.7)

    # ---------------- header
    def _draw_header(self, canvas: Image.Image, t: float, scene: SceneTimeline) -> None:
        L, colors = self.layout, self.template["colors"]
        if self._header_image is None:
            img = Image.new("RGBA", (L.width, L.progress_y + 40), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            header_font = font(self.template, "bold", L.f_header)
            spaced = " ".join(self.timeline.category.upper())
            hw = draw.textlength(spaced, font=header_font)
            draw.text(((L.width - hw) / 2, L.header_y), spaced, font=header_font,
                      fill=(*colors["accent"], 255))
            self._header_image = img
        canvas.alpha_composite(self._header_image, (0, 0))

        draw = ImageDraw.Draw(canvas)
        counter_font = font(self.template, "medium", L.f_counter)
        counter = f"Question {scene.index + 1} / {len(self.timeline.scenes)}"
        cw = draw.textlength(counter, font=counter_font)
        draw.text(((L.width - cw) / 2, L.counter_y), counter, font=counter_font,
                  fill=(*colors["muted"], 255))

        # progress bar with animated fill + glow head
        track = tuple(colors["progress_track"])
        accent = tuple(colors["accent"])
        x0 = (L.width - L.progress_w) / 2
        y0, bar_h = L.progress_y, 10
        scene_span = max(scene.end - scene.question_in, 0.001)
        frac = (scene.index + clamp01((t - scene.question_in) / scene_span)) / max(
            len(self.timeline.scenes), 1
        )
        draw.rounded_rectangle((x0, y0, x0 + L.progress_w, y0 + bar_h), bar_h // 2, fill=track)
        fill_w = max(bar_h, int(L.progress_w * frac))
        draw.rounded_rectangle((x0, y0, x0 + fill_w, y0 + bar_h), bar_h // 2, fill=(*accent, 255))
        pulse = 0.6 + 0.4 * math.sin(t * 3.2)
        hr = bar_h * (0.9 + 0.35 * pulse)
        hx, hy = x0 + fill_w, y0 + bar_h / 2
        draw.ellipse((hx - hr, hy - hr, hx + hr, hy + hr), fill=(*accent, int(120 * pulse) + 60))

    # ---------------- intro / outro
    def _draw_title_card(self, canvas: Image.Image, t: float, intro: bool) -> None:
        L, colors = self.layout, self.template["colors"]
        draw = ImageDraw.Draw(canvas)
        k = ease_out_cubic((t - (0.0 if intro else self.timeline.outro_in)) / 0.7)
        rise = (1 - k) * 40
        title = self.timeline.category.upper() if intro else "THANKS FOR WATCHING!"
        sub = (
            f"{len(self.timeline.scenes)} Questions  •  Can you get them all?"
            if intro
            else ("Follow for more!" if self.timeline.kind != "video" else "Like  •  Comment your score  •  Subscribe")
        )
        title_font, lines, line_h = fit_wrapped(
            self.template, "bold", title, L.width - 2 * L.margin // 2, L.f_title * 3, L.f_title
        )
        cy = L.height // 2 - (line_h * len(lines)) // 2 - 40 + rise
        glow_a = int(90 + 60 * math.sin(t * 2.0))
        for line in lines:
            wpx = draw.textlength(line, font=title_font)
            x = (L.width - wpx) / 2
            draw.text((x + 2, cy + 3), line, font=title_font, fill=(0, 0, 0, 120))
            draw.text((x, cy), line, font=title_font, fill=(*colors["text"], int(255 * k)))
            cy += line_h
        sub_font = font(self.template, "medium", max(L.f_counter, 24))
        sw = draw.textlength(sub, font=sub_font)
        draw.text(((L.width - sw) / 2, cy + 18), sub, font=sub_font,
                  fill=(*colors["accent"], min(255, glow_a + 120)))
        accent_w = int(120 + 40 * math.sin(t * 1.4))
        draw.rounded_rectangle(
            ((L.width - accent_w) / 2, cy + 8, (L.width + accent_w) / 2, cy + 12),
            2, fill=(*colors["accent2"], 200),
        )

    # ---------------- scene
    def _draw_scene(self, canvas: Image.Image, t: float, scene: SceneTimeline) -> None:
        L = self.layout
        sprites = self._scene_sprites(scene)
        exit_k = 1.0
        if scene.end - 0.3 <= t < scene.end:
            exit_k = 1.0 - (t - (scene.end - 0.3)) / 0.3

        # question card: slide up + fade
        qk = ease_out_cubic((t - scene.question_in) / 0.5)
        self._paste_glass(
            canvas, sprites.question_card,
            L.margin - PAD, L.question_y - PAD,
            alpha=qk * exit_k,
            dy=(1 - qk) * 46 + self._float_dy(t, 0.3, 2.5),
        )

        # options: pop-in, then reveal state
        n = len(scene.question.options)
        for i in range(n):
            t_in = scene.option_in[i]
            ok = (t - t_in) / 0.38
            if ok <= 0:
                continue
            scale = 0.9 + 0.1 * ease_out_back(ok)
            alpha = ease_out_cubic(ok)
            x, y = L.option_pos(i, n)
            dy = (1 - ease_out_cubic(ok)) * 24 + self._float_dy(t, i + 1.0, 2.2)
            extra_under, extra_over = None, None
            if t >= scene.reveal_at:
                rk = ease_out_cubic((t - scene.reveal_at) / 0.4)
                if i == scene.question.answer_index:
                    # pulse animates glow/border alpha, not scale — a per-frame
                    # scale change would force 5 image resizes every frame
                    pulse = 0.55 + 0.45 * math.sin((t - scene.reveal_at) * 3.6)
                    extra_under = (sprites.correct_glow, rk * (0.5 + 0.5 * pulse))
                    extra_over = [(sprites.correct_border, rk * (0.55 + 0.45 * pulse))]
                    if rk > 0.3:
                        icon = sprites.check_icon
                        ik = ease_out_back((t - scene.reveal_at - 0.12) / 0.4)
                        icon_scaled = icon
                        if ik < 1.0:
                            s = max(2, int(icon.width * (0.5 + 0.5 * ik)))
                            icon_scaled = icon.resize((s, s), Image.BILINEAR)
                        ix = x + L.option_w - icon_scaled.width - 18
                        iy = int(y + dy + (L.option_h - icon_scaled.height) / 2)
                        # draw after the card below
                        extra_check = (icon_scaled, ix, iy)
                    else:
                        extra_check = None
                else:
                    alpha *= 1.0 - rk * (1.0 - self.template["colors"]["wrong_dim"] / 255.0)
                    extra_check = None
            else:
                extra_check = None
            self._paste_glass(
                canvas, sprites.option_cards[i],
                x - PAD, y - PAD,
                alpha=alpha * exit_k, dy=dy, scale=scale,
                extra_under=extra_under, extra_over=extra_over,
            )
            if extra_check is not None:
                icon_img, ix, iy = extra_check
                faded = icon_img
                if exit_k < 1.0:
                    faded = icon_img.copy()
                    faded.putalpha(faded.getchannel("A").point(lambda v: int(v * exit_k)))
                canvas.alpha_composite(faded, (int(ix), int(iy)))

        # thinking countdown
        if scene.think_in <= t < scene.reveal_at:
            self._draw_countdown(canvas, t, scene, exit_k)

        # answer card
        if t >= scene.answer_in:
            ak = ease_out_cubic((t - scene.answer_in) / 0.45)
            aw = sprites.answer_card.w
            self._paste_glass(
                canvas, sprites.answer_card,
                (L.width - aw) // 2 - PAD, L.answer_y - PAD,
                alpha=ak * exit_k, dy=(1 - ak) * 42 + self._float_dy(t, 5.2, 1.8),
            )

        # explanation card
        if scene.explanation_in is not None and t >= scene.explanation_in and sprites.explanation_card:
            ek = ease_out_cubic((t - scene.explanation_in) / 0.5)
            self._paste_glass(
                canvas, sprites.explanation_card,
                L.margin - PAD, L.explanation_y - PAD,
                alpha=ek * exit_k, dy=(1 - ek) * 24 + self._float_dy(t, 7.7, 1.5),
            )

    def _draw_countdown(self, canvas: Image.Image, t: float, scene: SceneTimeline, exit_k: float) -> None:
        L, colors = self.layout, self.template["colors"]
        draw = ImageDraw.Draw(canvas)
        accent = tuple(colors["accent2"])
        label_font = font(self.template, "semibold", max(L.f_counter, 26))
        label = "Think..."
        lw = draw.textlength(label, font=label_font)

        if t < scene.countdown_in:
            pulse = 0.7 + 0.3 * math.sin(t * 4.0)
            draw.text(((L.width - lw) / 2, L.think_cy - label_font.size // 2), label,
                      font=label_font, fill=(*accent, int(255 * pulse * exit_k)))
            return

        elapsed = t - scene.countdown_in
        remaining = self.timeline.countdown_seconds - int(elapsed)
        if remaining < 1:
            return
        frac = elapsed - int(elapsed)
        pop = ease_out_back(frac / 0.35)
        digit_font = font(self.template, "bold", int(L.f_countdown * (0.7 + 0.3 * pop)))
        digit = str(remaining)
        dw = draw.textlength(digit, font=digit_font)
        cx, cy = L.width / 2, L.think_cy
        ring_r = L.f_countdown * 0.85
        sweep = 360 * (1 - frac)
        draw.arc(
            (cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r),
            start=-90, end=-90 + sweep,
            fill=(*accent, int(220 * exit_k)), width=6,
        )
        fade = 1.0 if frac < 0.7 else (1.0 - (frac - 0.7) / 0.3)
        draw.text((cx - dw / 2, cy - digit_font.size * 0.62), digit, font=digit_font,
                  fill=(*colors["text"], int(255 * fade * exit_k)))
        small = font(self.template, "medium", max(int(L.f_counter * 0.85), 20))
        sw = draw.textlength(label, font=small)
        draw.text((cx - sw / 2, cy + ring_r + 12), label, font=small,
                  fill=(*colors["muted"], int(210 * exit_k)))

    # ---------------- captions
    def _draw_captions(self, canvas: Image.Image, t: float) -> None:
        captions = self.timeline.captions
        while self._caption_ptr < len(captions) - 1 and t > captions[self._caption_ptr].end + 0.25:
            self._caption_ptr += 1
        if not captions:
            return
        chunk = captions[self._caption_ptr]
        if not (chunk.start - 0.1 <= t <= chunk.end + 0.25):
            return
        current = -1
        for i, w in enumerate(chunk.words):
            if w.start <= t:
                current = i
        key = (self._caption_ptr, current)
        if key != self._caption_cache:
            self._caption_cache = key
            self._caption_image = self._render_caption(chunk, current)
        if self._caption_image is not None:
            L = self.layout
            canvas.alpha_composite(
                self._caption_image,
                ((L.width - self._caption_image.width) // 2,
                 L.subtitle_y - self._caption_image.height // 2),
            )

    def _render_caption(self, chunk, current: int) -> Image.Image:
        L, colors = self.layout, self.template["colors"]
        fnt = font(self.template, "semibold", L.f_subtitle)
        probe = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
        space_w = probe.textlength(" ", font=fnt)
        widths = [probe.textlength(w.text, font=fnt) for w in chunk.words]
        total_w = int(sum(widths) + space_w * (len(widths) - 1))
        pad_x, pad_y = 26, 12
        img = Image.new("RGBA", (total_w + 2 * pad_x, L.f_subtitle + 2 * pad_y + 8), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle((0, 0, img.width - 1, img.height - 1), (img.height) // 2,
                               fill=(0, 0, 0, 130))
        x = pad_x
        for i, w in enumerate(chunk.words):
            color = tuple(colors["subtitle_highlight"]) if i == current else tuple(colors["subtitle"])
            draw.text((x, pad_y + 2), w.text, font=fnt, fill=(*color, 255))
            x += widths[i] + space_w
        return img
