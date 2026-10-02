"""Ploy Kickshaw sheets of "Why Ploy?" (img2258 to img2268): brown handwriting, labels
underlined with a red wave, in place of and in the style of the English text."""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from utils.images.fonts import find_font
from utils.images.game import BANDS, TARGET_BAND, original_image, split_bands

TEXT_COLOR = (85, 48, 48)
LINE_COLOR = (201, 42, 42)
SCALE_X = 0.87          # Segoe Print is wider than the original handwriting
SIZE_PER_HEIGHT = 0.89  # font size for an original line of a given height
ENTRY_PITCH = 2.2       # spacing between two entries (in font sizes)
LINE_PITCH = 1.4        # line spacing inside an entry
LIST_PITCH = 1.75       # spacing between two items of a numbered list
WAVE = dict(thickness=5, amplitude=3.5, period=36)  # underline, measured on the English
SS = 3                  # supersampling


def _font_path():
	return find_font('Segoe Print', 'segoepr.ttf', 'SEGOEPR.TTF')


def _masks(pixels, height):
	"""Areas covered by the text of each language."""
	return [pixels[b * height:(b + 1) * height, :, 3] > 60 for b in range(BANDS)]


def _original_metrics(band):
	"""Left edge, top and font size of the original text (brown text lines)."""
	dark = (band[:, :, 3] > 100) & (band[:, :, 0] < 150)
	lines, start = [], None
	for y, value in enumerate(np.append(dark.any(1), False)):
		if value and start is None:
			start = y
		elif not value and start is not None:
			lines.append((start, y))
			start = None
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


def _layout(fiche, size, entry_pitch, left, width):
	"""(x, y, text) positions in unsqueezed coordinates, underlines, total height."""
	font = ImageFont.truetype(_font_path(), round(size))
	texts, underlines, y = [], [], 0.0
	previous = None
	for number, (label, *paragraphs) in enumerate(fiche):
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


def _render(band_size, texts, underlines, font, size, top):
	"""Text and underline layers, drawn unsqueezed then shrunk horizontally."""
	width, height = band_size
	big = (round(width / SCALE_X * SS), height * SS)
	text_layer, line_layer = Image.new('L', big), Image.new('L', big)
	font_big = ImageFont.truetype(_font_path(), round(size * SS))
	text_draw, line_draw = ImageDraw.Draw(text_layer), ImageDraw.Draw(line_layer)
	ascent = font.getmetrics()[0]
	for x, y, text in texts:
		text_draw.text((x * SS, (top + y) * SS), text, font=font_big, fill=255)
	for x0, x1, y in underlines:
		_draw_wave(line_draw, x0 * SS, x1 * SS, (top + y + ascent + size * 0.3) * SS, SS)
	return [np.array(layer.resize(band_size, Image.LANCZOS)) for layer in (text_layer, line_layer)]


def _save(pixels, height, text_alpha, line_alpha, path):
	band = np.zeros((height, pixels.shape[1], 4), np.uint8)
	line = line_alpha.astype(np.float32) / 255
	text = text_alpha.astype(np.float32) / 255
	alpha = text + line * (1 - text)
	safe = np.maximum(alpha, 1e-6)[:, :, None]
	rgb = (np.array(TEXT_COLOR) * text[:, :, None] + np.array(LINE_COLOR) * (line * (1 - text))[:, :, None]) / safe
	band[:, :, :3] = np.clip(rgb, 0, 255).astype(np.uint8)
	band[:, :, 3] = np.clip(alpha * 255, 0, 255).astype(np.uint8)
	band[band[:, :, 3] == 0] = 0
	pixels[TARGET_BAND * height:(TARGET_BAND + 1) * height] = band
	Image.fromarray(pixels).save(path, optimize=True)


def generate(fiches: dict, captions: dict, out_dir) -> list[str]:
	written = []
	for key, fiche in fiches.items():
		number = int(key)
		pixels, height = split_bands(original_image(number))
		masks = _masks(pixels, height)
		left, top, size = _original_metrics(pixels[TARGET_BAND * height:(TARGET_BAND + 1) * height])
		# area covered by the 4 languages in the original image
		right = max(np.flatnonzero(m.any(0))[-1] for m in masks)
		bottom = max(np.flatnonzero(m.any(1))[-1] for m in masks)
		width = (right - left) / SCALE_X
		for scale in np.arange(1.0, 0.5, -0.02):
			pitch = ENTRY_PITCH if scale > 0.9 else ENTRY_PITCH * 0.85
			font, texts, underlines, total = _layout(fiche, size * scale, pitch, left / SCALE_X, width)
			if top + total <= bottom + 4:
				break
		text_alpha, line_alpha = _render((pixels.shape[1], height), texts, underlines, font, size * scale, top)
		_save(pixels, height, text_alpha, line_alpha, out_dir / f'img{number:04d}.png')
		written.append(f'img{number:04d}.png')

	# captions: one centered line, without underline
	for key, text in captions.items():
		number = int(key)
		pixels, height = split_bands(original_image(number))
		masks = _masks(pixels, height)
		_, top, size = _original_metrics(pixels[TARGET_BAND * height:(TARGET_BAND + 1) * height])
		xs = np.flatnonzero(masks[TARGET_BAND].any(0))
		center = (xs[0] + xs[-1]) / 2
		limit = 2 * min(center, max(np.flatnonzero(m.any(0))[-1] for m in masks) - center)
		while True:
			font = ImageFont.truetype(_font_path(), round(size))
			w = font.getlength(text) * SCALE_X
			if w <= limit:
				break
			size *= 0.97
		texts = [((center - w / 2) / SCALE_X, 0, text)]  # unsqueezed coordinates
		text_alpha, line_alpha = _render((pixels.shape[1], height), texts, [], font, size, top)
		_save(pixels, height, text_alpha, line_alpha, out_dir / f'img{number:04d}.png')
		written.append(f'img{number:04d}.png')
	return written
