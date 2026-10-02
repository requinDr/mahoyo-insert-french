"""White captions: the deduction captions (img1961 to img1967, white glow) and the quote
with its author (img1924, solid dark outline). The size, letter spacing, position, glow
and outline are measured on the English band, so only the text changes."""
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

from utils.images.fonts import find_font
from utils.images.game import BANDS, TARGET_BAND, original_image, split_bands

SS = 3  # supersampling
MIN_TRACKING = -0.02  # tightest letter spacing (in font sizes): some English lines are tight


def _font_path():
	return find_font('Helvetica Neue (Roman)', 'HelveticaNeueRoman.otf', 'HelveticaNeue-Roman.otf',
	                 'helveticaneue-roman.ttf', 'HelveticaNeue.ttc', 'arial.ttf', 'Arial.ttf')


def _core(band):
	"""Opaque light pixels: the letters without their halo (edges included, which turn
	grey over a dark halo)."""
	return (band[:, :, 3] >= 240) & (band[:, :, 0] > 128)


def _components_x(mask):
	"""Column ranges of the groups of ink separated by empty columns."""
	cols = np.append(mask.any(0), False)
	ranges, start = [], None
	for x, value in enumerate(cols):
		if value and start is None:
			start = x
		elif not value and start is not None:
			ranges.append((start, x))
			start = None
	return ranges


def _cap_height(mask):
	"""Height of the first letter (a capital in every English line)."""
	x0, x1 = _components_x(mask)[0]
	rows = np.flatnonzero(mask[:, x0:x1].any(1))
	return rows[-1] - rows[0] + 1, rows[-1] + 1  # height, baseline


def _letter_gap(mask, cap_height):
	"""Median width of the empty columns between two letters of a word (word spaces,
	wider, are left out)."""
	cols = mask.any(0)
	xs = np.flatnonzero(cols)
	gaps, run = [], 0
	for value in cols[xs[0]:xs[-1] + 1]:
		if not value:
			run += 1
		elif run:
			gaps.append(run)
			run = 0
	gaps = [g for g in gaps if g < cap_height * 0.3]
	return float(np.median(gaps)) if gaps else 0.0


def _render_line(text, font, tracking):
	"""Line mask at SS scale; returns the mask and the ascent offset of its baseline."""
	widths = [font.getlength(c) + tracking for c in text]
	ascent = font.getmetrics()[0]
	image = Image.new('L', (int(sum(widths) + font.size * 2), int(font.size * 2)))
	draw = ImageDraw.Draw(image)
	x = font.size * 0.5
	for c, w in zip(text, widths):
		draw.text((x, font.size * 0.5), c, font=font, fill=255)
		x += w
	mask = np.array(image)
	xs = np.flatnonzero(mask.max(0) > 0)
	return mask[:, xs[0]:xs[-1] + 1], font.size * 0.5 + ascent


def _font_for_cap_height(cap_height):
	reference = ImageFont.truetype(_font_path(), 100)
	box = reference.getbbox('H')
	return cap_height / ((box[3] - box[1]) / 100)


def _fit_tracking(text, size, english, cap_height):
	"""Letter spacing (in px at SS scale) giving the same gaps between letters as the English."""
	target = _letter_gap(english, cap_height)
	font = ImageFont.truetype(_font_path(), round(size * SS))
	best = None
	for tracking in np.arange(MIN_TRACKING, 0.5, 0.01) * font.size:
		mask, _ = _render_line(text, font, tracking)
		small = np.array(Image.fromarray(mask).resize((max(1, mask.shape[1] // SS), max(1, mask.shape[0] // SS)),
		                                              Image.LANCZOS)) > 128
		error = abs(_letter_gap(small, cap_height) - target)
		if best is None or error < best[0]:
			best = (error, tracking)
	return best[1]


def _fit_halo(band):
	"""Halo of the English text as (blur radius, strength): alpha ≈ strength × blur(letters)."""
	core = _core(band).astype(float) * 255
	alpha = band[:, :, 3].astype(float)
	around = ~ndimage.binary_dilation(core > 0, iterations=1) & ndimage.binary_dilation(core > 0, iterations=25)
	best = None
	for sigma in np.arange(1.0, 12.0, 0.5):
		blurred = ndimage.gaussian_filter(core, sigma)
		strength = (alpha[around] * blurred[around]).sum() / max((blurred[around] ** 2).sum(), 1e-6)
		error = ((alpha[around] - strength * blurred[around]) ** 2).mean()
		if best is None or error < best[0]:
			best = (error, sigma, strength)
	return best[1], best[2]


def _fit_outline(band):
	"""Solid outline of the English text as (radius, opacity): the opacity is constant
	around the letters, then drops at the radius."""
	core = _core(band)
	alpha = band[:, :, 3].astype(float)
	distance = ndimage.distance_transform_edt(~core)
	profile = [(r, alpha[(distance > r - 0.25) & (distance <= r)].mean()) for r in np.arange(0.5, 20, 0.25)
	           if ((distance > r - 0.25) & (distance <= r)).any()]
	opacity = np.median([a for r, a in profile if 2 <= r <= 4])
	radius = next(r for r, a in profile if r > 2 and a < opacity / 2)
	return radius, opacity


def _glow(letters, sigma, strength):
	return np.clip(ndimage.gaussian_filter(letters.astype(float), sigma) * strength / 255, 0, 1)


def _outline(letters, radius, opacity):
	distance = ndimage.distance_transform_edt(letters < 128)
	return np.clip(radius - distance, 0, 1) * opacity / 255


def _place(layer, mask, x, baseline, baseline_offset):
	"""Pastes a line mask (SS scale) with its left edge at x and its baseline at baseline (final px)."""
	piece = Image.fromarray(mask)
	layer.paste(piece, (int(round(x * SS)), int(round(baseline * SS - baseline_offset))), piece)


def _compose(pixels, height, letters, halo, halo_color, path):
	"""White letters over a halo (glow or outline, 0-1) of the given color, in the target band."""
	text = letters.astype(float) / 255
	alpha = text + halo * (1 - text)
	rgb = (255 * text[..., None] + np.array(halo_color) * (halo * (1 - text))[..., None]) / np.maximum(alpha, 1e-6)[..., None]
	band = np.zeros((height, pixels.shape[1], 4), np.uint8)
	band[..., :3] = np.clip(np.round(rgb), 0, 255)
	band[..., 3] = np.clip(np.round(alpha * 255), 0, 255)
	band[band[..., 3] == 0] = 0
	pixels[TARGET_BAND * height:(TARGET_BAND + 1) * height] = band
	Image.fromarray(pixels).save(path, optimize=True)


def _final(layer, width, height):
	return np.array(layer.resize((width, height), Image.LANCZOS))


def _max_right(pixels, height):
	"""Right edge of the area used by the 4 languages."""
	return max(np.flatnonzero((pixels[i * height:(i + 1) * height, :, 3] > 30).any(0))[-1] for i in range(BANDS))


def captions(texts: dict, out_dir) -> list[str]:
	"""One line per image, centered like the English, with a white glow."""
	written = []
	for key, text in texts.items():
		number = int(key)
		pixels, height = split_bands(original_image(number))
		band = pixels[TARGET_BAND * height:(TARGET_BAND + 1) * height]
		core = _core(band)
		cap, baseline = _cap_height(core)
		xs = np.flatnonzero(core.any(0))
		center = (xs[0] + xs[-1]) / 2
		limit = 2 * min(center, _max_right(pixels, height) - center)  # stays inside the original area
		size = _font_for_cap_height(cap)
		tracking = _fit_tracking(text, size, core, cap)
		while True:
			font = ImageFont.truetype(_font_path(), round(size * SS))
			mask, offset = _render_line(text, font, tracking)
			if mask.shape[1] / SS <= limit:
				break
			if tracking > MIN_TRACKING * font.size:
				tracking = max(MIN_TRACKING * font.size, tracking - 0.01 * font.size)  # tighten the spacing first
			else:
				size *= 0.98
		width = pixels.shape[1]
		layer = Image.new('L', (width * SS, height * SS))
		_place(layer, mask, center - mask.shape[1] / SS / 2, baseline, offset)
		letters = _final(layer, width, height)
		_compose(pixels, height, letters, _glow(letters, *_fit_halo(band)), (255, 255, 255),
		         out_dir / f'img{number}.png')
		written.append(f'img{number}.png')
	return written


def quote(config: dict, out_dir) -> str:
	"""Quote: left-aligned lines like the English ones, author right-aligned below, dark outline."""
	number = config['image']
	pixels, height = split_bands(original_image(number))
	band = pixels[TARGET_BAND * height:(TARGET_BAND + 1) * height]
	core = _core(band)
	# English layout: text lines then the author line, separated by empty rows
	rows = np.append(core.any(1), False)
	lines, start = [], None
	for y, value in enumerate(rows):
		if value and start is None:
			start = y
		elif not value and start is not None:
			lines.append((start, y))
			start = None
	*text_lines, author_line = lines
	left = np.flatnonzero(core[text_lines[0][0]:text_lines[0][1]].any(0))[0]
	author_right = np.flatnonzero(core[author_line[0]:author_line[1]].any(0))[-1]
	cap, first_baseline = _cap_height(core[text_lines[0][0]:text_lines[0][1]])
	first_baseline += text_lines[0][0]
	pitch = text_lines[1][0] - text_lines[0][0] if len(text_lines) > 1 else cap * 2.3
	_, author_baseline = _cap_height(core[author_line[0]:author_line[1]])
	author_baseline += author_line[0]
	limit = _max_right(pixels, height) - left

	size = _font_for_cap_height(cap)
	tracking = _fit_tracking(config['lines'][0], size, core[text_lines[0][0]:text_lines[0][1]], cap)
	while True:
		font = ImageFont.truetype(_font_path(), round(size * SS))
		masks = [_render_line(line, font, tracking) for line in config['lines']]
		if max(m.shape[1] for m, _ in masks) / SS <= limit:
			break
		if tracking > MIN_TRACKING * font.size:
			tracking = max(MIN_TRACKING * font.size, tracking - 0.01 * font.size)  # tighten the spacing first
		else:
			size *= 0.98
	# room for the lines above the author: tighten the line spacing if needed
	last_baseline = first_baseline + pitch * (len(masks) - 1)
	if last_baseline > author_baseline - cap * 1.8:
		pitch = (author_baseline - cap * 1.8 - first_baseline) / max(1, len(masks) - 1)

	width = pixels.shape[1]
	layer = Image.new('L', (width * SS, height * SS))
	for i, (mask, offset) in enumerate(masks):
		_place(layer, mask, left, first_baseline + i * pitch, offset)
	author, offset = _render_line(config['author'], font, tracking)
	_place(layer, author, author_right + 1 - author.shape[1] / SS, author_baseline, offset)
	letters = _final(layer, width, height)
	_compose(pixels, height, letters, _outline(letters, *_fit_outline(band)), (0, 0, 0),
	         out_dir / f'img{number}.png')
	return f'img{number}.png'
