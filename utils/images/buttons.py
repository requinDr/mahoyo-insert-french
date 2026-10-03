"""Buttons drawn on an opaque background (tabs of the settings): a grid of cells, one
button per column, one state per row (normal, hovered…). The English image exists in the
other languages with the same buttons and another text: the English text is erased with
their background; where all of them have text, the edges around are continued. Each label
is then written like its English one: centered, same height, letter spacing, color, glow."""
import numpy as np
from scipy import ndimage

from utils.images.effects import blur, fit_blur, over, ring
from utils.images.fonts import size_for_height
from utils.images.game import GameImage
from utils.images.inpaint import directional_fill
from utils.images.text import TextLayer, first_letter, fit_lines

MARGIN = 14  # px between a label that has to be reduced and the edges of its button


def _light(pixels):
	return pixels[..., :3].sum(-1)


def _erase(english, others):
	"""English image without its text (light letters and their glow)."""
	def text(layer, rest):
		return ndimage.binary_dilation(_light(layer) - np.min([_light(o) for o in rest], 0) > 40, iterations=6)
	layers = [english] + others
	masks = [text(layer, [o for j, o in enumerate(layers) if j != i]) for i, layer in enumerate(layers)]
	clean, hole = english.copy(), masks[0].copy()
	for other, mask in zip(others, masks[1:]):
		usable = hole & ~mask
		clean[usable] = other[usable]
		hole &= ~usable
	return directional_fill(clean, hole) if hole.any() else clean


def _label(original, clean, text):
	"""One cell redrawn: the new label with the color and the glow of the English one."""
	gain = _light(original) - _light(clean)
	letters = (gain > 0.5 * gain.max()) & (_light(original) > 600)
	cap, baseline = first_letter(letters)
	xs = np.flatnonzero(letters.any(0))
	center = (xs[0] + xs[-1] + 1) / 2
	button = np.flatnonzero((clean[..., 3] > 200).any(0))  # the button inside its cell
	limit = 2 * min(center - button[0], button[-1] + 1 - center) - 2 * MARGIN
	_, _, [(mask, offset)] = fit_lines([text], 'helvetica', size_for_height('helvetica', cap), letters, cap, limit)
	layer = TextLayer(original.shape[1], original.shape[0])
	layer.paste_centered(mask, offset, center, baseline)
	alpha = layer.alpha()
	# glow: the English one around its letters, as an opacity of its color over the background
	around = ring(letters, 1, 12) & (gain > 15)
	result = clean
	if around.sum() > 50:
		color = np.median(original[around & (gain > np.percentile(gain[around], 75))][:, :3], 0)
		span = np.maximum(_light(color[None, None]) - _light(clean), 1)
		opacity = np.clip(gain / span, 0, 1)
		sigma, strength = fit_blur(letters, opacity, ring(letters, 1, 12), np.arange(1.0, 8.0, 0.5))
		result = over(result, color, blur(alpha, sigma, strength))
	return over(result, np.median(original[letters][:, :3], 0), alpha)


def glow_tabs(image: GameImage, config: dict):
	"""config: {"texts": label of each column, "states": number of rows}."""
	original = image.target
	clean = _erase(original, image.language_variants())
	columns, rows = len(config['texts']), config['states']
	width, height = image.width // columns, image.height // rows
	result = clean.copy()
	for row in range(rows):
		for column, text in enumerate(config['texts']):
			cell = (slice(row * height, (row + 1) * height), slice(column * width, (column + 1) * width))
			result[cell] = _label(original[cell], clean[cell], text)
	image.target = result
