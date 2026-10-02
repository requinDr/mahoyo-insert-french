"""Lines replaced one by one in an image with a transparent background (menus, help
pages): each box [left, top, right, bottom, text] holds one English line, which is removed;
the new line is written at its place (same left edge, baseline, size, letter spacing and
color), tightened then reduced if it is wider than the box."""
import numpy as np

from utils.images.effects import over
from utils.images.fonts import size_for_height
from utils.images.game import GameImage
from utils.images.text import TextLayer, first_letter, fit_lines


def text_boxes(image: GameImage, config: dict):
	"""config: {"font": name in FONTS (Helvetica Neue by default), "boxes": [[x0, y0, x1, y1, text], …]}."""
	font_name = config.get('font', 'helvetica')
	original, result = image.target.copy(), image.target.copy()
	for x0, y0, x1, y1, text in config['boxes']:
		area = original[y0:y1, x0:x1]
		letters = area[..., 3] > 128
		if not letters.any():
			raise ValueError(f'{image.name} : pas de texte dans la zone {[x0, y0, x1, y1]}')
		cap, baseline = first_letter(letters)
		left = x0 + np.flatnonzero(letters.any(0))[0]
		_, _, [(mask, offset)] = fit_lines([text], font_name, size_for_height(font_name, cap), letters, cap, x1 - left)
		layer = TextLayer(image.width, image.height)
		layer.paste(mask, offset, left, y0 + baseline)
		result[y0:y1, x0:x1] = 0  # the English line, on a transparent background
		result = over(result, np.median(area[area[..., 3] > 250][:, :3], 0), layer.alpha())
	image.target = result
