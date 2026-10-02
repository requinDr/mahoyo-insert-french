"""Text painted into a full-screen background: the English text is erased (see inpaint),
then the new text is drawn at the place and in the style of the English one."""
import numpy as np
from PIL import Image
from scipy import ndimage

from utils.images.effects import over
from utils.images.fonts import load_font, size_for_height
from utils.images.game import GameImage
from utils.images.inpaint import erase_text, grid_shifts
from utils.images.text import SS, TextLayer, render_line


def _sum_rgb(band):
	return band[..., :3].sum(-1)


def _stretched(text, font, tracking=0.0, stretch=1.0):
	mask, offset = render_line(text, font, tracking)
	if stretch != 1.0:
		mask = np.array(Image.fromarray(mask).resize((int(mask.shape[1] * stretch), mask.shape[0]), Image.LANCZOS))
	return mask, offset


def warning(image: GameImage, config: dict):
	"""Warning before the bonus chapter (img1955): dark red title and tilted text on a
	sheet of grid paper, with a soft shadow."""
	background = erase_text(image, _sum_rgb, -1, 12, 14, shifts=grid_shifts(109))  # grid cell: 109 px
	# title: in place of "Warning" (center x 1047, baseline 396)
	title = TextLayer(image.width, image.height)
	title.paste_centered(*render_line(config['title'], load_font('palatino', 62 * SS), 2 * SS), 1047, 396)
	# body: lines centered on x 1057, 52 px apart, tilted by 1.8° like the English
	lines = config['lines']
	size = 38 * SS
	longest = max(load_font('palatino', size).getlength(line) + 0.06 * size * len(line) for line in lines) / SS
	if longest > 1100:
		size = int(size * 1100 / longest)
	font = load_font('palatino', size)
	center_y, pitch = 622, 52
	first = center_y - pitch * (len(lines) - 1) / 2
	body = TextLayer(image.width, image.height)
	for i, line in enumerate(lines):
		body.paste_centered(*render_line(line, font, 0.06 * font.size), 1057, first + i * pitch + 12)
	body_alpha = body.alpha(body.canvas.rotate(1.8, resample=Image.BICUBIC, center=(1057 * SS, center_y * SS)))
	title_alpha = title.alpha()
	shadow = np.clip(ndimage.gaussian_filter(np.maximum(title_alpha, body_alpha), 3) * 0.35, 0, 1)
	result = over(background, (90, 60, 50), shadow)
	result = over(result, (113, 3, 3), title_alpha)
	image.target = over(result, (76, 32, 32), body_alpha)


def apology(image: GameImage, text: str):
	"""Apology over a sky (img2256): one wide white line."""
	background = erase_text(image, _sum_rgb, 1, 10, 10)
	# English: size 74, stretched by 1.21, centered on x 1125, baseline around 645
	stretch, size = 1.1, 74
	natural = load_font('helvetica', size * SS).getlength(text) / SS
	size = min(size, int(size * 2000 / (natural * stretch)))  # fits in 2000 px
	layer = TextLayer(image.width, image.height)
	layer.paste_centered(*_stretched(text, load_font('helvetica', size * SS), stretch=stretch), 1125, 645)
	image.target = over(background, (255, 255, 255), layer.alpha())


def speech_bubble(image: GameImage, text: str):
	"""Speech bubble (img2091): handwritten text, tilted like the English one, in a plain bubble."""
	background = erase_text(image, _sum_rgb, -1, 40, 5)
	original = image.target
	ink = (background[..., :3].sum(-1) - original[..., :3].sum(-1)) > 150
	ys, xs = np.nonzero(ink)
	center_x, center_y = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
	# tilt: slope of the bottom of the letters (the English line has no descenders)
	columns = np.unique(xs)
	slope = np.polyfit(columns, [ys[xs == x].max() for x in columns], 1)[0]
	angle = np.degrees(np.arctan(slope))
	letter_height = (ys.max() - ys.min()) - abs(slope) * (xs.max() - xs.min())
	# same length as the English line, without letters taller than the English ones
	line_width = (xs.max() - xs.min()) / np.cos(np.radians(angle))
	size = min(line_width / (load_font('segoe_print_bold', 100).getlength(text) / 100),
	           1.4 * size_for_height('segoe_print_bold', letter_height, 'T'))
	layer = TextLayer(image.width, image.height)
	layer.paste_centered(*render_line(text, load_font('segoe_print_bold', size * SS)), center_x, center_y + letter_height / 2)
	letters = layer.alpha(layer.canvas.rotate(-angle, resample=Image.BICUBIC, center=(center_x * SS, center_y * SS)))
	image.target = over(background, np.median(original[ink][:, :3], 0), letters)
