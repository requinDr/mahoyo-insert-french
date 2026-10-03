"""Lines replaced one by one in an image with a plain background, transparent or of one
color (menus, help pages, settings, warning screen): each box [left, top, right, bottom,
text] holds one English line, which is removed; the new text is written at its place
(same edge, baseline, size, letter spacing and color), tightened then reduced if it is
wider than the box. A text with "\n"
is written on several lines, centered vertically on the English line."""
from statistics import median

import numpy as np

from utils.images.effects import over
from utils.images.fonts import load_font, size_for_height
from utils.images.game import GameImage
from utils.images.text import MIN_TRACKING, SS, TextLayer, first_letter, fit_lines, fit_tracking

LINE_PITCH = 1.45  # spacing of the lines of a text written on several lines, in cap heights


def _background(area):
	"""Plain background of a box (most of its pixels): transparent, or a flat color."""
	background = np.median(area.reshape(-1, 4), 0)
	return background if background[3] > 128 else np.zeros(4)


def _letters(area):
	"""Letters of a box: opaque pixels on a transparent background, or pixels clearly
	different from a flat background."""
	background = _background(area)
	if background[3] == 0:
		return area[..., 3] > 128
	return np.abs(area - background).max(-1) > 96


def text_boxes(image: GameImage, config: dict):
	"""config: {"font": name in FONTS (Helvetica Neue by default),
	"align": "left" (default), "right" or "center", like the English lines,
	"spacing": "english" (default: letter spacing of each English line) or "uniform" (the
	median of the English lines, the same for all), "boxes": [[x0, y0, x1, y1, text], …]}."""
	font_name = config.get('font', 'helvetica')
	align = config.get('align', 'left')
	original, result = image.target.copy(), image.target.copy()
	measured = []
	for x0, y0, x1, y1, text in config['boxes']:
		letters = _letters(original[y0:y1, x0:x1])
		if not letters.any():
			raise ValueError(f'{image.name} : pas de texte dans la zone {[x0, y0, x1, y1]}')
		measured.append((letters, *first_letter(letters)))
	spacing = None
	if config.get('spacing', 'english') == 'uniform':
		spacings = []
		for (*_, text), (letters, cap, _) in zip(config['boxes'], measured):
			font = load_font(font_name, size_for_height(font_name, cap) * SS)
			spacings.append(fit_tracking(text.split('\n')[0], font, letters, cap, MIN_TRACKING) / font.size)
		spacing = median(spacings)
	for (x0, y0, x1, y1, text), (letters, cap, baseline) in zip(config['boxes'], measured):
		area = original[y0:y1, x0:x1]
		cols = np.flatnonzero(letters.any(0))
		left, right = x0 + cols[0], x0 + cols[-1] + 1
		limit = {'left': x1 - left, 'right': right - x0, 'center': x1 - x0}[align]
		lines = text.split('\n')
		_, _, rendered = fit_lines(lines, font_name, size_for_height(font_name, cap), letters, cap, limit, spacing)
		first_baseline = y0 + baseline - LINE_PITCH * cap * (len(lines) - 1) / 2
		layer = TextLayer(image.width, image.height)
		for i, (mask, offset) in enumerate(rendered):
			width = mask.shape[1] / SS
			x = {'left': left, 'right': right - width, 'center': (x0 + x1 - width) / 2}[align]
			layer.paste(mask, offset, x, first_baseline + i * LINE_PITCH * cap)
		result[y0:y1, x0:x1] = _background(area)  # the English line removed
		result = over(result, np.median(area[letters & (area[..., 3] > 250)][:, :3], 0), layer.alpha())
	image.target = result
