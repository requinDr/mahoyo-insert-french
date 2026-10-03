"""Light text on a transparent band, with a glow or an outline measured on the English
text: deduction captions (img1961 to img1968) and archive chapter names (glow), quote (img1924, dark outline),
outlined blocks (img2397, dark outline). The size and letter spacing are the English ones."""
import numpy as np
from scipy import ndimage

from utils.images.effects import blur, fit_blur, fit_outline, outline, over, ring
from utils.images.fonts import load_font, size_for_height
from utils.images.game import GameImage
from utils.images.text import MIN_TRACKING, SS, TextLayer, first_letter, fit_lines, fit_tracking, render_line, runs

def _letters(band):
	"""Opaque light pixels: the letters without their halo (edges included, which turn grey
	over a dark halo)."""
	return (band[..., 3] >= 240) & (band[..., 0] > 128)


def _draw(image, letters, effect, color, letter_color=(255, 255, 255)):
	"""Letters (white by default) over their glow or outline, on a transparent band."""
	result = over(np.zeros_like(image.target), color, effect)
	image.target = over(result, letter_color, letters)


def _small_end(core, cap):
	"""Smaller text ending the English line ("Chapter 5 - Part 1"): its cap height and the
	gap before it, or None. It is made of the last letters, all shorter than the capitals."""
	parts = []
	for x0, x1 in runs(core.any(0)):
		rows = np.flatnonzero(core[:, x0:x1].any(1))
		parts.append((x0, x1, rows[-1] - rows[0] + 1))
	small = []
	while parts and parts[-1][2] < 0.85 * cap:
		small.append(parts.pop())
	if not small or not parts:
		return None
	return max(h for _, _, h in small), small[-1][0] - parts[-1][1]


def _glow_line(band, text, right, spacing=None, align='center'):
	"""Band redrawn with one line, placed like its English line, with a glow; size, letter
	spacing, colors and opacity of the letters and of the glow are the English ones.
	right: right edge of the area the line must stay in.
	spacing: letter spacing in font sizes (measured on the English line by default).
	align: 'center' (default), 'left' or 'right': what the line keeps of the English one,
	its center or its left or right edge.
	Returns the band and the letter spacing used."""
	alpha = band[..., 3]
	strongest = alpha.max()
	# letters, possibly half transparent (inactive buttons): the most opaque pixels
	core = alpha >= 0.94 * strongest
	core &= band[..., 0] >= 0.5 * np.percentile(band[core][:, 0], 90)
	# their color: the lightest of them (a strong glow is opaque too, but darker)
	light = band[..., :3].sum(-1)
	letter_color = np.median(band[core & (light >= np.percentile(light[core], 75))][:, :3], 0)
	cap, baseline = first_letter(core)
	xs = np.flatnonzero(core.any(0))
	center = (xs[0] + xs[-1]) / 2
	glow = np.flatnonzero((alpha > 0).any(0))  # room left for the glow at the edges
	limit = {'center': 2 * min(center, right - center),  # inside the original area
	         'left': right - (glow[-1] - xs[-1]) - xs[0],
	         'right': xs[-1] - (xs[0] - glow[0])}[align]
	small_text = text.get('small') if isinstance(text, dict) else None
	main_text = text['text'] if isinstance(text, dict) else text
	if small_text is None:
		font, tracking, [(mask, offset)] = fit_lines([main_text], 'helvetica', size_for_height('helvetica', cap), core, cap,
		                                          limit, spacing)
		half = mask.shape[1] / SS / 2
		pieces = [(mask, offset, {'center': 0.0, 'left': xs[0] + half - center, 'right': xs[-1] + 1 - half - center}[align])]
	else:
		small_cap, gap = _small_end(core, cap)
		size = size_for_height('helvetica', cap)
		while True:  # both parts reduced together until they fit
			font, tracking, [(mask, offset)] = fit_lines([main_text], 'helvetica', size, core, cap, float('inf'), spacing)
			ratio = small_cap / cap
			small_font = load_font('helvetica', font.size * ratio)
			small_mask, small_offset = render_line(small_text, small_font, tracking * ratio)
			width = (mask.shape[1] + small_mask.shape[1]) / SS + gap
			if width <= limit:
				break
			size *= 0.98
		left = center - width / 2
		pieces = [(mask, offset, left - center + mask.shape[1] / SS / 2),
		          (small_mask, small_offset, left + mask.shape[1] / SS + gap - center + small_mask.shape[1] / SS / 2)]
	layer = TextLayer(band.shape[1], band.shape[0])
	for mask, offset, shift in pieces:
		layer.paste_centered(mask, offset, center + shift, baseline)
	letters = layer.alpha()
	opacity = alpha / strongest
	glow = (alpha > 0.04 * strongest) & (alpha < 0.47 * strongest) & ~ndimage.binary_dilation(core, iterations=2)
	result = np.zeros_like(band)
	if glow.sum() > 0.5 * core.sum():  # no glow: only the antialiasing of the letters
		effect = blur(letters, *fit_blur(core, opacity, ring(core, 1, 25)))
		result = over(result, np.median(band[glow][:, :3], 0), effect * strongest / 255)
	return over(result, letter_color, letters * strongest / 255), tracking / font.size


def glow_caption(image: GameImage, text):
	"""One line, centered like the English one, with a glow; the colors of the letters and of
	the glow are the English ones (deduction captions, chapter names of the archive).
	text: a string, or {"text": …, "small": …} where "small" is written after it in smaller
	letters, like the end of the English line (sizes and gap measured on it)."""
	right, _ = image.ink_bounds(30)
	image.target, _ = _glow_line(image.target, text, right)


def glow_buttons(image: GameImage, config: dict):
	"""Button whose states (normal, hovered…) are side by side in equal cells, each a line
	with a glow: config {"text": …, "states": number of cells}. The letter spacing is
	measured on the first state (a strong glow merges the letters) and kept for all."""
	width = image.width // config['states']
	result = image.target.copy()
	spacing = None
	for i in range(config['states']):
		cell = result[:, i * width:(i + 1) * width]
		cell[:], measured = _glow_line(cell.copy(), config['text'], width, spacing)
		spacing = measured if spacing is None else spacing
	image.target = result


def option_labels(image: GameImage, config: dict):
	"""Labels at both ends of a setting (Low / High…), one state per row (hovered with a
	glow, normal without): config {"texts": [left, right], "rows": number of states}.
	Each word is redrawn like its English one, the left one ending and the right one
	starting where the English words do, with the natural letter spacing of the font:
	these words are too short (2 or 3 gaps) to measure the English spacing, which matches
	the natural one (their widths agree within 0.02 font size)."""
	height, width = image.height // config['rows'], image.width // 2
	result = image.target.copy()
	for column, (text, align) in enumerate(zip(config['texts'], ('right', 'left'))):
		for row in range(config['rows']):
			cell = result[row * height:(row + 1) * height, column * width:(column + 1) * width]
			cell[:], _ = _glow_line(cell.copy(), text, width, spacing=0.0, align=align)
	image.target = result


def quote(image: GameImage, config: dict):
	"""Left-aligned lines like the English ones, author right-aligned below, dark outline."""
	band = image.target
	core = _letters(band)
	*text_lines, author_line = runs(core.any(1))  # English: text lines, then the author line
	first = core[text_lines[0][0]:text_lines[0][1]]
	left = np.flatnonzero(first.any(0))[0]
	cap, first_baseline = first_letter(first)
	first_baseline += text_lines[0][0]
	pitch = text_lines[1][0] - text_lines[0][0] if len(text_lines) > 1 else cap * 2.3
	author = core[author_line[0]:author_line[1]]
	author_right = np.flatnonzero(author.any(0))[-1]
	author_baseline = author_line[0] + first_letter(author)[1]
	right, _ = image.ink_bounds(30)
	font, tracking, rendered = fit_lines(config['lines'], 'helvetica', size_for_height('helvetica', cap), first, cap,
	                                limit=right - left)
	# room for the lines above the author: tighten the line spacing if needed
	pitch = min(pitch, (author_baseline - cap * 1.8 - first_baseline) / max(1, len(rendered) - 1))
	layer = TextLayer(image.width, image.height)
	for i, (mask, offset) in enumerate(rendered):
		layer.paste(mask, offset, left, first_baseline + i * pitch)
	mask, offset = render_line(config['author'], font, tracking)
	layer.paste(mask, offset, author_right + 1 - mask.shape[1] / SS, author_baseline)
	letters = layer.alpha()
	_draw(image, letters, outline(letters, *fit_outline(core, band[..., 3] / 255)), (0, 0, 0))


def outlined_blocks(image: GameImage, blocks: list[list[str]]):
	"""Blocks of bold text with a dark outline: each English block (top to bottom) is replaced
	by the matching new lines; several lines are left-aligned like the English ones, a
	single line is centered on the English one."""
	band = image.target
	core = _letters(band)
	labels, _ = ndimage.label(ndimage.binary_dilation(core, iterations=20))
	boxes = sorted(ndimage.find_objects(labels), key=lambda box: (box[0].start, box[1].start))
	if len(boxes) != len(blocks):
		raise ValueError(f'{image.name} : {len(boxes)} blocs de texte dans l\'image, {len(blocks)} dans le JSON')
	measured = []
	for box, lines in zip(boxes, blocks):
		block = core[box] & (labels[box] > 0)
		english_lines = runs(block.any(1))
		first = block[english_lines[0][0]:english_lines[0][1]]
		measured.append((box, lines, block, english_lines, first, *first_letter(first)))
	# letter spacing (in font sizes) measured on the longest block: a few letters are not enough
	_, lines, _, _, first, cap, _ = max(measured, key=lambda m: m[4].shape[1])
	font = load_font('helvetica_bold', size_for_height('helvetica_bold', cap, ) * SS)
	spacing = fit_tracking(lines[0], font, first, cap, MIN_TRACKING) / font.size
	layer = TextLayer(image.width, image.height)
	for box, lines, block, english_lines, first, cap, baseline in measured:
		top, left = box[0].start, box[1].start
		baseline += top + english_lines[0][0]
		pitch = (english_lines[1][0] - english_lines[0][0]) if len(english_lines) > 1 else cap * 1.6
		font = load_font('helvetica_bold', size_for_height('helvetica_bold', cap) * SS)
		xs = np.flatnonzero(block.any(0))
		for i, line in enumerate(lines):
			mask, offset = render_line(line, font, spacing * font.size)
			if len(english_lines) > 1:
				layer.paste(mask, offset, left + xs[0], baseline + i * pitch)
			else:
				layer.paste_centered(mask, offset, left + (xs[0] + xs[-1]) / 2, baseline + i * pitch)
	letters = layer.alpha()
	_draw(image, letters, outline(letters, *fit_outline(core, band[..., 3] / 255)), (0, 0, 0))
