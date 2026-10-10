"""Images of "Why Ploy?": lesson titles (img2167 to img2172, big rounded red letters on one
line), sheets of the Ploy Kickshaws (img2258 to img2268, brown handwriting, labels
underlined with a red wave), their captions (img2259), and the archive thumbnails of the
lessons (nz1 to nz6). Transparent bands: the English text is simply replaced; the
thumbnails have their background redrawn from the original background image."""
import math

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

from utils.images.effects import over
from utils.images.fonts import load_font, size_for_height
from utils.images.game import GameImage, original_image
from utils.images.inpaint import directional_fill, fill_from_bands
from utils.images.text import TextLayer, first_letter, fit_lines, runs

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
MIN_ENTRY_PITCH = 1.75  # tightest spacing, before reducing the size
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
	"""One entry per item: [underlined label or None, paragraph, paragraph…]. The sheet may be
	as wide as the widest language, but not lower than the English one: the game hides what
	lies below it."""
	left, top, size = _metrics(image.target)
	right, _ = image.ink_bounds(60)  # width used by the 4 languages
	bottom = np.flatnonzero((image.target[..., 3] > 60).any(1))[-1]
	width = (right - left) / SCALE_X
	original = image.target.copy()
	# the entries get closer before the letters get smaller
	for scale, pitch in ((s, p) for s in np.arange(1.0, 0.5, -0.02) for p in np.arange(ENTRY_PITCH, MIN_ENTRY_PITCH, -0.1)):
		font, texts, underlines, _ = _layout(entries, size * scale, pitch, left / SCALE_X, width)
		image.target = original
		_draw_handwriting(image, texts, underlines, font, size * scale, top)
		if np.flatnonzero((image.target[..., 3] > 60).any(1))[-1] <= bottom:
			break


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


# ---------- Archive thumbnails ----------

THUMBNAIL_MARGIN = 4  # px left on each side of a line that has to be reduced
THUMBNAIL_FONT = 'helvetica_heavy'  # the English is a heavy sans serif


def _background_view(background, band, rows=40):
	"""The background image as it appears in the band (scaled down and cropped): the scale
	and offset matching the top and bottom rows of the band, where there is no text."""
	ys, xs = np.nonzero(background[..., 3] > 0)
	content = Image.fromarray(background[:ys.max() + 1, :xs.max() + 1].astype(np.uint8))
	height, width = band.shape[:2]
	reference = np.concatenate([band[:rows], band[-rows:]])[..., :3]
	best = None
	for w in range(width + 20, width + 50, 2):
		h = round(w * content.height / content.width)
		small = np.array(content.resize((w, h), Image.LANCZOS)).astype(float)
		for oy in range(h - height + 1):
			for ox in range(w - width + 1):
				view = small[oy:oy + height, ox:ox + width]
				error = np.abs(np.concatenate([view[:rows], view[-rows:]])[..., :3] - reference).mean()
				if best is None or error < best[0]:
					best = (error, view)
	return best[1]


def _text_masks(image):
	"""Red text of each band, only where the bands differ (the red of the drawing, the same in
	every band, is not text)."""
	stack = np.stack([band[..., :3] for band in image.bands])
	differs = ndimage.binary_dilation((np.abs(stack - np.median(stack, 0)).max(-1) > 30).any(0), iterations=3)
	red = (stack[..., 0] > stack[..., 1] + 50) & (stack[..., 0] > stack[..., 2] + 50)
	return [ndimage.binary_dilation(mask, iterations=2) & differs for mask in red]


def _background_from_bands(image):
	"""Target band without its text, when the background is made of several layers: the
	bands are the same apart from their text, so it comes from the others; where all the
	languages have text, the lines and edges around are continued."""
	masks = _text_masks(image)
	clean, hole = fill_from_bands(image, masks, masks[image.target_band])
	return directional_fill(clean, hole) if hole.any() else clean


def thumbnail(image: GameImage, config: dict):
	"""Archive thumbnail (nz1 to nz6): the title in dark red heavy letters, centered over a
	scaled-down background. config: {"background": number of the background image, "text": …};
	the background is matched on the band. Without "background" (background made of
	several layers), it is rebuilt from the other language bands. The line is written with
	the English size, letter spacing, center and color, reduced if wider than the thumbnail."""
	band = image.target
	r, g, b = band[..., 0], band[..., 1], band[..., 2]
	letters = (r > 120) & (g < 80) & (b < 80) & _text_masks(image)[image.target_band]
	# the line of text: the rows holding most of these pixels (not stray red specks)
	top, bottom = max(runs(letters.any(1)), key=lambda run: letters[run[0]:run[1]].sum())
	letters[:top] = letters[bottom:] = False
	cap, baseline = first_letter(letters)
	xs = np.flatnonzero(letters.any(0))
	center = (xs[0] + xs[-1] + 1) / 2
	limit = 2 * min(center, image.width - center) - 2 * THUMBNAIL_MARGIN
	_, _, [(mask, offset)] = fit_lines([config['text']], THUMBNAIL_FONT, size_for_height(THUMBNAIL_FONT, cap),
	                                   letters, cap, limit)
	layer = TextLayer(image.width, image.height)
	layer.paste_centered(mask, offset, center, baseline)
	if 'background' in config:
		background = np.array(original_image(int(config['background'])).convert('RGBA')).astype(float)
		view = _background_view(background, band)
	else:
		view = _background_from_bands(image)
	image.target = over(view, np.median(band[letters][:, :3], 0), layer.alpha())
