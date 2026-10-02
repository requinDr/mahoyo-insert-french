"""Images of "Why Ploy?": lesson titles (img2167 to img2172, big rounded red letters on one
line), sheets of the Ploy Kickshaws (img2258 to img2268, brown handwriting, labels
underlined with a red wave) and their captions (img2259). Transparent bands: the English
text is simply replaced."""
import math

import numpy as np
from PIL import Image, ImageDraw

from utils.images.effects import over
from utils.images.fonts import load_font
from utils.images.game import GameImage
from utils.images.text import runs

# ---------- Lesson titles ----------

TITLE_COLOR = (189, 0, 0)
TITLE_MAX_WIDTH = 1866  # width of the English lines that fill the band
TITLE_CENTER = 940      # horizontal center of the English lines
MIN_SCALE_X = 0.9       # horizontal squeeze allowed before reducing the size
TITLE_SS = 4            # supersampling


def _digit_box(alpha):
	"""Top and bottom of the leading digit (the bottom is the baseline)."""
	cols = alpha.max(0) > 128
	x0 = np.flatnonzero(cols)[0]
	x1 = x0 + np.flatnonzero(~cols[x0:])[0]
	rows = np.flatnonzero(alpha[:, x0:x1].max(1) > 128)
	return rows[0], rows[-1] + 1


def _render_title(text, size):
	"""Text as a mask, stroke thickened like the English, thin space before ! and ?."""
	font = load_font('arial_rounded', size)
	stroke = round(size * 0.018)
	pieces, x = [], 0.0
	for i, c in enumerate(text):
		if c == ' ' and i + 1 < len(text) and text[i + 1] in '!?':
			x += font.getlength(' ') * 0.5
			continue
		pieces.append((x, c))
		x += font.getlength(c)
		if i + 1 < len(text) and text[i + 1] != ' ':
			x += font.getlength(c + text[i + 1]) - font.getlength(c) - font.getlength(text[i + 1])  # kerning
	image = Image.new('L', (int(x + size * 2), size * 3), 0)
	draw = ImageDraw.Draw(image)
	for px, c in pieces:
		draw.text((px + size, size), c, font=font, fill=255, stroke_width=stroke, stroke_fill=255)
	return np.array(image)


def title(image: GameImage, text: str):
	band = image.target
	top, base = _digit_box(band[..., 3])
	# size at which the digit is as tall as the original digit
	mask = _render_title(text, 100 * TITLE_SS)
	t, b = _digit_box(mask)
	scale = (base - top) / ((b - t) / TITLE_SS) / TITLE_SS
	cols = np.flatnonzero(mask.max(0) > 0)
	width = (cols[-1] - cols[0] + 1) * scale
	original = np.flatnonzero(band[..., 3].max(0) > 128)
	max_width = min(TITLE_MAX_WIDTH, original[-1] - original[0] + 1)  # no wider than the original
	scale_x = scale * min(1.0, max_width / width)
	if scale_x < scale * MIN_SCALE_X:
		scale = scale_x / MIN_SCALE_X
	crop = Image.fromarray(mask[:, cols[0]:cols[-1] + 1])
	w, h = round(crop.width * scale_x), round(crop.height * scale)
	small = np.array(crop.resize((w, h), Image.LANCZOS)).astype(float) / 255
	# digit baseline on the original one, shared horizontal center
	y0, x0 = round(base - b * scale), round(TITLE_CENTER - w / 2)
	alpha = np.zeros(band.shape[:2])
	ys, xs = max(0, y0), max(0, x0)
	alpha[ys:y0 + h, xs:x0 + w] = small[ys - y0:min(h, band.shape[0] - y0), xs - x0:min(w, band.shape[1] - x0)]
	image.target = over(np.zeros_like(band), TITLE_COLOR, np.clip(alpha, 0, 1))


# ---------- Sheets and captions ----------

TEXT_COLOR = (85, 48, 48)
LINE_COLOR = (201, 42, 42)
SCALE_X = 0.87          # Segoe Print is wider than the original handwriting
SIZE_PER_HEIGHT = 0.89  # font size for an original line of a given height
ENTRY_PITCH = 2.2       # spacing between two entries (in font sizes)
LINE_PITCH = 1.4        # line spacing inside an entry
LIST_PITCH = 1.75       # spacing between two items of a numbered list
WAVE = dict(thickness=5, amplitude=3.5, period=36)  # underline, measured on the English
SS = 3                  # supersampling


def _metrics(band):
	"""Left edge, top and font size of the original text (brown text lines)."""
	dark = (band[..., 3] > 100) & (band[..., 0] < 150)
	lines = runs(dark.any(1))
	heights = [b - a for a, b in lines if b - a > 15]
	return np.flatnonzero(dark.any(0))[0], lines[0][0], float(np.median(heights)) * SIZE_PER_HEIGHT


def _wrap(text, font, width):
	lines, current = [], ''
	for word in text.split(' '):
		candidate = f'{current} {word}' if current else word
		if current and font.getlength(candidate) > width:
			lines.append(current)
			current = word
		else:
			current = candidate
	return lines + [current]


def _layout(entries, size, entry_pitch, left, width):
	"""(x, y, text) positions in unsqueezed coordinates, underlines, total height."""
	font = load_font('segoe_print', size)
	texts, underlines, y = [], [], 0.0
	previous = None
	for number, (label, *paragraphs) in enumerate(entries):
		if number:
			# list items (without label) are closer together, as in English
			y += (LIST_PITCH if label is None and previous is None else entry_pitch) * size
		previous = label
		x = left
		if label:
			head = f'{label} : '
			texts.append((x, y, head))
			underlines.append((x, x + font.getlength(label), y))
			x += font.getlength(head)
			indent = x if x - left < width * 0.45 else left + 2 * size
		else:  # "2- text": wrapped lines align after the number
			indent = left + font.getlength(paragraphs[0].split(' ')[0] + ' ')
		first = True
		for paragraph in paragraphs:
			for line in _wrap(paragraph, font, left + width - (x if first else indent)):
				if not first:
					y += LINE_PITCH * size
				texts.append((x if first else indent, y, line))
				first = False
	return font, texts, underlines, y + LINE_PITCH * size


def _draw_wave(draw, x0, x1, y, scale):
	# drawn before the horizontal squeeze: widen the period accordingly
	t, a, p = WAVE['thickness'] * scale, WAVE['amplitude'] * scale, WAVE['period'] / SCALE_X * scale
	points = [(x, y + a * math.sin((x - x0) / p * 2 * math.pi + 0.6 * math.sin((x - x0) / (p * 2.7))))
	          for x in np.arange(x0, x1, 1.0)]
	draw.line(points, fill=255, width=round(t), joint='curve')


def _draw_handwriting(image, texts, underlines, font, size, top):
	"""Text and underlines, drawn unsqueezed then shrunk horizontally, on a transparent band."""
	big = (round(image.width / SCALE_X * SS), image.height * SS)
	text_layer, line_layer = Image.new('L', big), Image.new('L', big)
	font_big = load_font('segoe_print', size * SS)
	text_draw, line_draw = ImageDraw.Draw(text_layer), ImageDraw.Draw(line_layer)
	ascent = font.getmetrics()[0]
	for x, y, text in texts:
		text_draw.text((x * SS, (top + y) * SS), text, font=font_big, fill=255)
	for x0, x1, y in underlines:
		_draw_wave(line_draw, x0 * SS, x1 * SS, (top + y + ascent + size * 0.3) * SS, SS)
	text_alpha, line_alpha = [np.array(layer.resize((image.width, image.height), Image.LANCZOS)).astype(float) / 255
	                          for layer in (text_layer, line_layer)]
	result = over(np.zeros_like(image.target), LINE_COLOR, line_alpha)
	image.target = over(result, TEXT_COLOR, text_alpha)


def sheet(image: GameImage, entries: list):
	"""One entry per item: [underlined label or None, paragraph, paragraph…]."""
	left, top, size = _metrics(image.target)
	right, bottom = image.ink_bounds(60)  # area used by the 4 languages
	width = (right - left) / SCALE_X
	for scale in np.arange(1.0, 0.5, -0.02):
		pitch = ENTRY_PITCH if scale > 0.9 else ENTRY_PITCH * 0.85
		font, texts, underlines, total = _layout(entries, size * scale, pitch, left / SCALE_X, width)
		if top + total <= bottom + 4:
			break
	_draw_handwriting(image, texts, underlines, font, size * scale, top)


def caption(image: GameImage, text: str):
	"""One centered line, without underline."""
	_, top, size = _metrics(image.target)
	xs = np.flatnonzero((image.target[..., 3] > 60).any(0))
	center = (xs[0] + xs[-1]) / 2
	right, _ = image.ink_bounds(60)
	limit = 2 * min(center, right - center)
	while (width := load_font('segoe_print', size).getlength(text) * SCALE_X) > limit:
		size *= 0.97
	font = load_font('segoe_print', size)
	_draw_handwriting(image, [((center - width / 2) / SCALE_X, 0, text)], [], font, size, top)
