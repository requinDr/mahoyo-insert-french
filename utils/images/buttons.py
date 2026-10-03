"""Buttons drawn on an opaque background (tabs of the settings): a grid of cells, one
button per column, one state per row (normal, hovered…). The English image exists in the
other languages with the same buttons and another text, which shows where the English text
is; it is erased by continuing the button around it. Each label
is then written like its English one: centered, same height, letter spacing, color, glow."""
import numpy as np
from scipy import ndimage

from utils.images.effects import blur, fit_blur, over, ring
from utils.images.fonts import size_for_height
from utils.images.game import GameImage
from utils.images.text import TextLayer, first_letter, fit_lines

GLOW = 8     # extent of the glow around the letters (px)
BUTTON_ALPHA = 20  # the buttons may be half transparent, their surroundings are not drawn
BORDER = 4   # thickness of the frame of a button (px), never redrawn
MARGIN = 14  # px between a label that has to be reduced and the edges of its button


def _light(pixels):
	"""Brightness as displayed: the buttons may be half transparent."""
	return pixels[..., :3].sum(-1) * pixels[..., 3] / 255


def _erase_cell(cell, text):
	"""One cell without its text: inside the button, the band holding the text and its glow
	(from the top of the button, so that no seam crosses its gloss) is filled row by row
	between the button just left and just right of it: the button changes from top to
	bottom, hardly from left to right."""
	clean = cell.copy()
	inner = ndimage.binary_erosion(cell[..., 3] > BUTTON_ALPHA, iterations=BORDER)  # inside the frame
	text &= inner
	if not text.any():
		return clean
	rows, cols = np.flatnonzero(text.any(1)), np.flatnonzero(text.any(0))
	inside_rows, inside_cols = np.flatnonzero(inner.any(1)), np.flatnonzero(inner.any(0))
	x0 = max(cols[0] - GLOW, inside_cols[0] + 2)
	x1 = min(cols[-1] + 1 + GLOW, inside_cols[-1] - 1)
	t = (np.arange(x0, x1) - (x0 - 1)) / (x1 - x0 + 1)
	for y in range(inside_rows[0], min(rows[-1] + 1 + GLOW, inside_rows[-1] + 1)):
		left, right = cell[y, x0 - 1], cell[y, x1]
		clean[y, x0:x1] = left * (1 - t[:, None]) + right * t[:, None]
	return clean


def _label(original, clean, text):
	"""One cell redrawn: the new label with the color (light or dark) and the glow of the
	English one."""
	gain = _light(original) - _light(clean)
	dark = np.median(gain[np.abs(gain) > 0.5 * np.abs(gain).max()]) < 0  # dark text on a light button
	if dark:
		gain = -gain
		letters = gain > 0.5 * gain.max()
	else:
		letters = (gain > 0.5 * gain.max()) & (_light(original) > 600)
	cap, baseline = first_letter(letters)
	xs = np.flatnonzero(letters.any(0))
	center = (xs[0] + xs[-1] + 1) / 2
	# the button inside its cell: the columns at least half as opaque as its body (not the
	# thin glow around its frame)
	opacity = clean[..., 3].mean(0)
	button = np.flatnonzero(opacity > 0.5 * opacity.max())
	limit = 2 * min(center - button[0], button[-1] + 1 - center) - 2 * MARGIN
	_, _, [(mask, offset)] = fit_lines([text], 'helvetica', size_for_height('helvetica', cap), letters, cap, limit)
	layer = TextLayer(original.shape[1], original.shape[0])
	layer.paste_centered(mask, offset, center, baseline)
	alpha = layer.alpha()
	# glow: the English one around its letters, as an opacity of its color over the background
	around = ring(letters, 1, 12) & (gain > 15)
	result = clean
	if not dark and around.sum() > 50:
		color = np.median(original[around & (gain > np.percentile(gain[around], 75))][:, :3], 0)
		span = np.maximum(color.sum() - _light(clean), 1)
		opacity = np.clip(gain / span, 0, 1)
		sigma, strength = fit_blur(letters, opacity, ring(letters, 1, 12), np.arange(1.0, 8.0, 0.5))
		result = over(result, color, blur(alpha, sigma, strength))
	return over(result, np.median(original[letters][:, :3], 0), alpha)


def glow_tabs(image: GameImage, config: dict):
	"""config: {"texts": label of each column, "states": number of rows}. Buttons whose
	states are side by side repeat their label in "texts", with "states": 1."""
	original = image.target
	# the English text: where the image differs from the same one in every other language
	text = np.min([np.abs(_light(original) - _light(o)) for o in image.language_variants()], 0) > 60
	columns, rows = len(config['texts']), config['states']
	width, height = image.width // columns, image.height // rows
	result = original.copy()
	for row in range(rows):
		for column, label in enumerate(config['texts']):
			cell = (slice(row * height, (row + 1) * height), slice(column * width, (column + 1) * width))
			found = text[cell].copy()
			if found.sum() < 50:  # same text as the other languages there: contrast with the button
				inner = original[cell][..., 3] > BUTTON_ALPHA
				found = np.abs(_light(original[cell]) - np.median(_light(original[cell])[inner])) > 60
			clean = _erase_cell(original[cell], found)
			result[cell] = _label(original[cell], clean, label)
	image.target = result
