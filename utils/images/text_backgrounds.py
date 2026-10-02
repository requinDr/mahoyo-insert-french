"""Full-screen images with text painted into the background: img1955 (warning before the
bonus chapter) and img2256 (apology over a sky).

1. The background without text is rebuilt in the band to replace from the other bands,
   which have the same background with text placed elsewhere; what is left (where all
   languages have text) is filled with pieces shifted by one cell of the paper grid
   (img1955) or by diffusion (plain sky of img2256).
2. The text is drawn in the style of the English (positions measured on the English image).
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy import ndimage

from utils.images.fonts import find_font
from utils.images.game import BANDS, TARGET_BAND, original_image, split_bands

SS = 3  # text supersampling


# ---------- Background without text ----------

def _patch_fill(img, hole, shifts, block=24):
	"""Fills the hole block by block with a shifted piece of the already clean image,
	using the shift that best matches the block's surroundings."""
	out, hole = img.copy(), hole.copy()
	height, width = hole.shape
	ys, xs = np.nonzero(hole)
	for by in range(ys.min() // block * block, ys.max() + 1, block):
		for bx in range(xs.min() // block * block, xs.max() + 1, block):
			part = np.zeros_like(hole)
			part[by:by + block, bx:bx + block] = hole[by:by + block, bx:bx + block]
			if not part.any():
				continue
			ring = np.zeros_like(hole)
			y0, y1, x0, x1 = max(0, by - 8), min(height, by + block + 8), max(0, bx - 8), min(width, bx + block + 8)
			ring[y0:y1, x0:x1] = ~hole[y0:y1, x0:x1]
			cy, cx = np.nonzero(part)
			ry, rx = np.nonzero(ring)
			best = None
			for dy, dx in shifts:
				sy, sx, qy, qx = cy + dy, cx + dx, ry + dy, rx + dx
				if min(sy.min(), sx.min(), qy.min(initial=0), qx.min(initial=0)) < 0:
					continue
				if max(sy.max(), qy.max(initial=0)) >= height or max(sx.max(), qx.max(initial=0)) >= width:
					continue
				if hole[sy, sx].any():
					continue
				error = ((out[qy, qx, :3] - out[ry, rx, :3]) ** 2).mean() if len(ry) else 0
				if best is None or error < best[0]:
					best = (error, dy, dx)
			if best:
				_, dy, dx = best
				out[cy, cx] = out[cy + dy, cx + dx]
				hole[cy, cx] = False
	return out, hole


def _diffuse(img, mask, iterations=400):
	out = img.copy()
	out[mask] = img[~mask].mean(0)
	for _ in range(iterations):
		out[mask] = ndimage.uniform_filter(out, (7, 7, 1))[mask]
	return out


def _clean_background(number, text_is_dark, shifts=None, threshold=12, halo=14):
	"""Image pixels, band height, and the band to replace without its text."""
	pixels, height = split_bands(original_image(number))
	pixels = pixels.astype(float)
	bands = np.stack([pixels[i * height:(i + 1) * height] for i in range(BANDS)])
	lum = bands[..., :3].sum(-1)
	sign = -1 if text_is_dark else 1

	def text_mask(i):  # difference from the background estimated by the other bands (lightest or darkest)
		others = np.stack([lum[j] for j in range(BANDS) if j != i])
		reference = others.max(0) if text_is_dark else others.min(0)
		mask = ndimage.binary_opening((lum[i] - reference) * sign > threshold)
		return ndimage.binary_dilation(mask, iterations=halo)

	masks = [text_mask(i) for i in range(BANDS)]
	target = bands[TARGET_BAND].copy()
	hole = ndimage.binary_dilation(masks[TARGET_BAND], iterations=3)
	for i in range(BANDS):
		if i == TARGET_BAND:
			continue
		usable = hole & ~masks[i]
		target[usable] = bands[i][usable]
		hole &= ~usable
	if shifts and hole.any():
		target, hole = _patch_fill(target, hole, shifts)
	if hole.any():
		ys, xs = np.nonzero(hole)
		y0, y1, x0, x1 = max(0, ys.min() - 20), ys.max() + 20, max(0, xs.min() - 20), xs.max() + 20
		target[y0:y1, x0:x1] = _diffuse(target[y0:y1, x0:x1], hole[y0:y1, x0:x1])
	return pixels, height, target


# ---------- Text ----------

def _draw_line(layer, text, font, center_x, baseline_y, tracking=0.0, stretch=1.0):
	"""Centered line, with letter spacing and horizontal stretch."""
	widths = [font.getlength(c) + tracking for c in text]
	total = (sum(widths) - tracking) * stretch
	ascent = font.getmetrics()[0]
	line = Image.new('L', (int(sum(widths) + font.size * 2), int(font.size * 2)))
	draw = ImageDraw.Draw(line)
	x = font.size * 0.5
	for c, w in zip(text, widths):
		draw.text((x, font.size * 0.5), c, font=font, fill=255)
		x += w
	line = line.resize((int(line.width * stretch), line.height), Image.LANCZOS)
	layer.paste(line, (int(round(center_x - total / 2 - font.size * 0.5 * stretch)),
	                   int(round(baseline_y - ascent - font.size * 0.5))), line)


def _layer(width, height, draw):
	layer = Image.new('L', (width * SS, height * SS))
	draw(layer)
	return layer


def _final(layer, width, height):
	return np.array(layer.resize((width, height), Image.LANCZOS)).astype(float)


def _composite(background, alpha, color):
	a = alpha[..., None] / 255.0
	out = background.copy()
	out[..., :3] = background[..., :3] * (1 - a) + np.array(color) * a
	return out


def _save(pixels, height, band, path):
	pixels[TARGET_BAND * height:(TARGET_BAND + 1) * height] = band
	Image.fromarray(np.clip(np.round(pixels), 0, 255).astype(np.uint8)).save(path, optimize=True)


def warning(config: dict, out_dir) -> str:
	"""Warning: dark red title and tilted text on a sheet of paper."""
	number = config['image']
	period = 109  # paper grid spacing
	steps = (0, period, -period, 2 * period, -2 * period)
	shifts = [(dy, dx) for dy in steps for dx in steps + (3 * period, -3 * period, 4 * period, -4 * period)
	          if (dy, dx) != (0, 0)]
	pixels, height, background = _clean_background(number, text_is_dark=True, shifts=shifts)
	width = pixels.shape[1]
	font_path = find_font('Palatino Linotype', 'pala.ttf', 'Palatino Linotype.ttf', 'Palatino.ttc')

	# title: in place of "Warning" (center x 1047, height 349-408)
	title_font = ImageFont.truetype(font_path, 62 * SS)
	title = _layer(width, height, lambda layer: _draw_line(
		layer, config['titre'], title_font, 1047 * SS, 396 * SS, tracking=2 * SS))

	# body: lines centered on x 1057, 52 px apart, tilted by 1.8° like the English
	lines = config['lignes']
	body_font = ImageFont.truetype(font_path, 38 * SS)
	tracking = 0.06 * body_font.size
	longest = max(sum(body_font.getlength(c) + tracking for c in line) for line in lines) / SS
	scale = min(1.0, 1100 / longest)
	if scale < 1:
		body_font = ImageFont.truetype(font_path, int(38 * SS * scale))
		tracking = 0.06 * body_font.size
	center_y, pitch = 622, 52
	first = center_y - pitch * (len(lines) - 1) / 2

	def draw_body(layer):
		for i, line in enumerate(lines):
			_draw_line(layer, line, body_font, 1057 * SS, (first + i * pitch + 12) * SS, tracking=tracking)
	body = _layer(width, height, draw_body).rotate(1.8, resample=Image.BICUBIC, center=(1057 * SS, center_y * SS))

	title_a, body_a = _final(title, width, height), _final(body, width, height)
	# soft shadow under the text, like the English
	shadow = np.array(Image.fromarray(np.maximum(title_a, body_a).astype(np.uint8))
	                  .filter(ImageFilter.GaussianBlur(3))).astype(float) * 0.35
	result = _composite(background, shadow, (90, 60, 50))
	result = _composite(result, title_a, (113, 3, 3))
	result = _composite(result, body_a, (76, 32, 32))
	_save(pixels, height, result, out_dir / f'img{number}.png')
	return f'img{number}.png'


def apology(config: dict, out_dir) -> str:
	"""Apology: one wide white line over the sky."""
	number = config['image']
	pixels, height, background = _clean_background(number, text_is_dark=False, threshold=10, halo=10)
	width = pixels.shape[1]
	font_path = find_font('Helvetica Neue (Roman)', 'HelveticaNeueRoman.otf', 'HelveticaNeue-Roman.otf',
	                      'helveticaneue-roman.ttf', 'HelveticaNeue.ttc')
	# English: size 74, stretched by 1.21, centered on x 1125, baseline around 645
	text = config['texte']
	stretch, size = 1.1, 74
	natural = ImageFont.truetype(font_path, size * SS).getlength(text) / SS
	size = min(size, int(size * 2000 / (natural * stretch)))  # fits in 2000 px
	font = ImageFont.truetype(font_path, size * SS)
	alpha = _final(_layer(width, height, lambda layer: _draw_line(
		layer, text, font, 1125 * SS, 645 * SS, stretch=stretch)), width, height)
	_save(pixels, height, _composite(background, alpha, (255, 255, 255)), out_dir / f'img{number}.png')
	return f'img{number}.png'
