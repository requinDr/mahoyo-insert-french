"""Drawing text lines and measuring the English text they replace.

Text is drawn SS times larger, then reduced: the letters get smooth edges and can be
placed to a fraction of a pixel. Positions are given in final pixels.
"""
import numpy as np
from PIL import Image, ImageDraw

from utils.images.fonts import load_font

SS = 3  # supersampling
MIN_TRACKING = -0.02  # tightest letter spacing (in font sizes): some English lines are tight


def render_line(text: str, font, tracking: float = 0.0) -> tuple[np.ndarray, float]:
	"""Mask of one line (font scale, cropped to its ink) and the distance from its top to
	the baseline. tracking is added after every letter."""
	widths = [font.getlength(c) + tracking for c in text]
	image = Image.new('L', (int(sum(widths) + font.size * 2), int(font.size * 2)))
	draw = ImageDraw.Draw(image)
	x = font.size * 0.5
	for c, w in zip(text, widths):
		draw.text((x, font.size * 0.5), c, font=font, fill=255)
		x += w
	mask = np.array(image)
	cols = np.flatnonzero(mask.max(0) > 0)
	return mask[:, cols[0]:cols[-1] + 1], font.size * 0.5 + font.getmetrics()[0]


class TextLayer:
	"""Supersampled canvas of the size of a band, where lines are pasted."""

	def __init__(self, width: int, height: int):
		self.size = (width, height)
		self.canvas = Image.new('L', (width * SS, height * SS))

	def paste(self, mask: np.ndarray, offset: float, x: float, baseline: float):
		"""Pastes a line from render_line (mask, offset) with its left edge at x and its
		baseline at baseline."""
		piece = Image.fromarray(mask)
		self.canvas.paste(piece, (int(round(x * SS)), int(round(baseline * SS - offset))), piece)

	def paste_centered(self, mask: np.ndarray, offset: float, center: float, baseline: float):
		self.paste(mask, offset, center - mask.shape[1] / SS / 2, baseline)

	def alpha(self, canvas: Image.Image | None = None) -> np.ndarray:
		"""Opacity of the letters (0-1) at the band size."""
		return np.array((canvas or self.canvas).resize(self.size, Image.LANCZOS)).astype(float) / 255


def runs(values: np.ndarray) -> list[tuple[int, int]]:
	"""Ranges [start, stop) of consecutive True values."""
	padded = np.concatenate([[False], values, [False]]).astype(np.int8)
	edges = np.flatnonzero(np.diff(padded))
	return list(zip(edges[::2], edges[1::2]))


def first_letter(mask: np.ndarray) -> tuple[int, int]:
	"""Cap height and baseline of a line, from its first letter sitting on the baseline
	(quotes and parentheses, above or below it, are skipped)."""
	parts = []
	for x0, x1 in runs(mask.any(0)):
		rows = np.flatnonzero(mask[:, x0:x1].any(1))
		parts.append((rows[-1] - rows[0] + 1, rows[-1] + 1))
	tallest = max(h for h, _ in parts)
	baseline = np.median([bottom for h, bottom in parts if h >= tallest / 2])  # quotes are short
	# round letters overshoot the baseline a little; parentheses go further below it
	tolerance = max(1.5, 0.04 * tallest)
	on_line = [(h, bottom) for h, bottom in parts if abs(bottom - baseline) <= tolerance]
	tallest = max(h for h, _ in on_line)
	return next((h, bottom) for h, bottom in on_line if h >= 0.7 * tallest)


def letter_gap(mask: np.ndarray, cap: float) -> float:
	"""Median width of the empty columns between two letters of a word (word spaces, wider,
	are left out)."""
	cols = mask.any(0)
	ink = np.flatnonzero(cols)
	gaps = [b - a for a, b in runs(~cols[ink[0]:ink[-1] + 1]) if b - a < cap * 0.3]
	return float(np.median(gaps)) if gaps else 0.0


def fit_tracking(text: str, font, english: np.ndarray, cap: float, low: float = 0.0, high: float = 0.5) -> float:
	"""Letter spacing (font scale) giving the same gaps between letters as the English
	line `english` (mask, final scale), searched between low and high font sizes."""
	target = letter_gap(english, cap)
	best = None
	for tracking in np.arange(low, high, 0.01) * font.size:
		mask, _ = render_line(text, font, tracking)
		small = np.array(Image.fromarray(mask).resize((max(1, mask.shape[1] // SS), max(1, mask.shape[0] // SS)),
		                                              Image.LANCZOS)) > 128
		error = abs(letter_gap(small, cap) - target)
		if best is None or error < best[0]:
			best = (error, tracking)
	return best[1]


def fit_lines(text_lines, font_name, size, english, cap, limit, spacing=None):
	"""Font, letter spacing (font scale) and rendered lines (render_line): size and letter
	spacing of the English line `english` (mask), or the given spacing (in font sizes),
	then tightened and reduced until the longest line fits in limit pixels."""
	tracking = None
	while True:
		font = load_font(font_name, size * SS)
		if tracking is None:
			tracking = (spacing * font.size if spacing is not None
			            else fit_tracking(text_lines[0], font, english, cap, MIN_TRACKING))
		rendered = [render_line(line, font, tracking) for line in text_lines]
		if max(mask.shape[1] for mask, _ in rendered) / SS <= limit:
			return font, tracking, rendered
		if tracking > MIN_TRACKING * font.size:
			tracking = max(MIN_TRACKING * font.size, tracking - 0.01 * font.size)  # tighten the spacing first
		else:
			size *= 0.98
