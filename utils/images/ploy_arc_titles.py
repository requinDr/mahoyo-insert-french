"""Logos of "The Wonderful World of Ploys" (img2111, img2112, img2174, img2175): a red title in heavy rounded
letters with a dark red drop shadow, the first line bent along an arc, over a yellow disc
(or nothing). The English title is erased: outside the disc the band is made transparent;
inside, the disc is continued over it, and its edge is redrawn on the ellipse fitted to the
visible part of the edge."""
import itertools
import math

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

from utils.images.effects import over
from utils.images.fonts import load_font, size_for_height
from utils.images.game import GameImage
from utils.images.inpaint import directional_fill
from utils.images.text import SS

FONT = 'arial_rounded'
MIN_LETTER = 150         # smaller red parts are not letters (px)
STROKE = 0.03            # thickening of the letters (in font sizes): the English ones are heavier
MAX_SPAN = 1.0           # a line may take up to this much of the English angle (flowers at the ends)
DISC_EDGE_WIDTH = 0.012  # thickness of the darker edge of the disc, relative to its radius


def _red(band):
	"""Text and its shadow, with their smoothed edges: red, without the orange flowers."""
	r, g, b, a = (band[..., i] for i in range(4))
	flowers = ndimage.binary_dilation((a > 200) & (r > 200) & (g > 0.45 * r) & (g < 0.75 * r) & (b < 60),
	                                  iterations=3)
	return (a > 20) & (r > g + 60) & (r > b + 60) & ~flowers


def _letters(band):
	r, g, b, a = (band[..., i] for i in range(4))
	return (a > 200) & (r > 215) & (g < 90) & (b < 90)


def _erase(band, hole):
	"""Band without its title: transparent outside the disc, disc continued inside."""
	clean = band.copy()
	r, g, b, a = (band[..., i] for i in range(4))
	yellow = (a > 200) & (r > 150) & (g > 0.75 * r) & (b < 120) & ~hole  # not the orange flowers
	if yellow.sum() < 20000:  # no disc
		clean[hole] = 0
		return clean
	# ellipse with horizontal axes, a x² + b y² + c x + d y = 1, on the visible edge of the disc
	edge = yellow & ndimage.binary_dilation(a < 30, iterations=2) & ~ndimage.binary_dilation(hole, iterations=6)
	ys, xs = np.nonzero(edge)
	ka, kb, kc, kd = np.linalg.lstsq(np.column_stack([xs * xs, ys * ys, xs, ys]).astype(float),
	                                 np.ones(len(xs)), rcond=None)[0]
	cx, cy = -kc / (2 * ka), -kd / (2 * kb)
	k = 1 + ka * cx * cx + kb * cy * cy
	Y, X = np.mgrid[:band.shape[0], :band.shape[1]].astype(float)
	distance = np.hypot((X - cx) / math.sqrt(k / ka), (Y - cy) / math.sqrt(k / kb))  # 1 on the edge
	inside = distance < 1
	clean[hole & ~inside] = 0
	filled = directional_fill(clean, hole | ~inside)
	clean[hole & inside] = filled[hole & inside]
	rim = hole & inside & (distance > 1 - DISC_EDGE_WIDTH)
	clean[rim, :3] = np.median(band[(distance > 1 - DISC_EDGE_WIDTH) & inside & ~hole][:, :3], 0)
	clean[rim, 3] = 255
	return clean


def _circle(points):
	"""Circle (cx, cy, R) through points (y, x), least squares."""
	y, x = points[:, 0], points[:, 1]
	a, b, c = np.linalg.lstsq(np.column_stack([x, y, np.ones_like(x)]), x * x + y * y, rcond=None)[0]
	cx, cy = a / 2, b / 2
	return cx, cy, math.sqrt(c + cx * cx + cy * cy)


def _lines(letters):
	"""English lines, top to bottom, and the center of their arcs: the letters on the arc of
	the first line (the circle through the most letter centers), then the others."""
	labels, count = ndimage.label(letters)
	sizes = ndimage.sum(letters, labels, range(1, count + 1))
	parts = [i + 1 for i in range(count) if sizes[i] > MIN_LETTER]
	centers = np.array(ndimage.center_of_mass(letters, labels, parts))
	boxes = ndimage.find_objects(labels)
	height = np.median([boxes[p - 1][0].stop - boxes[p - 1][0].start for p in parts])
	best = None
	for triple in itertools.combinations(range(len(centers)), 3):
		try:
			cx, cy, radius = _circle(centers[list(triple)])
		except np.linalg.LinAlgError:
			continue
		if cy < centers[:, 0].max() or radius > 5000:  # center below the text
			continue
		inliers = (np.abs(np.hypot(centers[:, 1] - cx, centers[:, 0] - cy) - radius) < height * 0.3).sum()
		if best is None or inliers > best[0]:
			best = (inliers, cx, cy, radius)
	_, cx, cy, radius = best
	# the other lines are clearly nearer the center: split at the widest gap of the distances
	offsets = np.hypot(centers[:, 1] - cx, centers[:, 0] - cy) - radius
	ordered = np.sort(offsets)
	gap = np.argmax(np.diff(ordered))
	first = offsets > (ordered[gap] + ordered[gap + 1]) / 2
	lines = [np.isin(labels, [p for p, keep in zip(parts, group) if keep]) for group in (first, ~first)]
	cx, cy, _ = _circle(centers[first])
	return lines, cx, cy


def _arc(line, cx, cy):
	"""Arc of an English line around (cx, cy): center, baseline radius, cap height, middle
	and width of its angle. Each letter stands on the baseline (its point nearest the
	center); the cap height is that of the tallest letters."""
	labels, count = ndimage.label(line)
	ys, xs = np.nonzero(line)
	radius = np.hypot(xs - cx, ys - cy)
	angle = np.arctan2(xs - cx, cy - ys)  # 0 straight up, positive to the right
	inner = ndimage.minimum(radius, labels[ys, xs], range(1, count + 1))
	outer = ndimage.maximum(radius, labels[ys, xs], range(1, count + 1))
	baseline = float(np.median(inner))
	cap = float(np.percentile(outer - baseline, 90))
	return cx, cy, baseline, cap, (angle.min() + angle.max()) / 2, angle.max() - angle.min()


def _draw_arc_line(layer, text, cx, cy, baseline, cap, middle, span):
	"""Letters along the arc, centered on the angle middle, each turned along the arc."""
	size = size_for_height(FONT, cap)
	while True:
		font = load_font(FONT, size * SS)
		length = (font.getlength(text) + STROKE * font.size * len(text)) / SS
		if length / baseline <= span * MAX_SPAN:
			break
		size *= 0.97
	start = middle - length / baseline / 2
	box = int(font.size * 2)
	for i, char in enumerate(text):
		if char == ' ':
			continue
		position = (font.getlength(text[:i]) + STROKE * font.size * (i + 0.5) + font.getlength(char) / 2) / SS
		phi = start + position / baseline
		glyph = Image.new('L', (box, box))
		stroke = round(STROKE * font.size)
		ImageDraw.Draw(glyph).text((box / 2, box / 2), char, font=font, fill=255, anchor='ms',
		                            stroke_width=stroke, stroke_fill=255)
		glyph = glyph.rotate(-math.degrees(phi), resample=Image.BICUBIC, center=(box / 2, box / 2))
		x, y = cx + baseline * math.sin(phi), cy - baseline * math.cos(phi)
		layer.paste(glyph, (round(x * SS - box / 2), round(y * SS - box / 2)), glyph)


def arc_title(image: GameImage, config: dict):
	"""config: {"lines": new lines, top to bottom, "scale": letter height relative to the
	English (1 by default)}. With as many lines as the English title, each one replaces an
	English line; otherwise the lines are spread over the height of the English title, on
	arcs of the same center (the first English line's), the line spacing scaled likewise."""
	lines, scale = config['lines'], config.get('scale', 1.0)
	band = image.target
	red = _red(band)
	letters = _letters(band)
	shadow_only = red & ~letters
	# shadow: the letters shifted, measured where it matches the dark red best
	best = None
	for dy in range(16):
		for dx in range(16):
			moved = np.roll(np.roll(letters, dy, 0), dx, 1)
			score = (moved & shadow_only).sum() - (moved & ~red).sum()
			if best is None or score > best[0]:
				best = (score, dx, dy)
	_, dx, dy = best
	shadow_color = np.median(band[shadow_only & np.roll(np.roll(letters, dy, 0), dx, 1)][:, :3], 0)
	letter_color = np.median(band[letters][:, :3], 0)

	english, cx, cy = _lines(letters)
	clean = _erase(band, ndimage.binary_dilation(red, iterations=5))
	arcs = [_arc(line, cx, cy) for line in english if line.any()]
	if len(lines) == len(arcs):
		placed = [(baseline, cap * scale, middle, span) for _, _, baseline, cap, middle, span in arcs]
	else:
		# English title from the baseline of its last line to the top of its first one
		_, _, top_baseline, top_cap, middle, span = arcs[0]
		bottom = arcs[-1][2]
		pitch = (top_baseline - bottom) / max(1, len(arcs) - 1) * scale
		cap = top_cap * scale
		height = cap + pitch * (len(lines) - 1)
		first = (top_baseline + top_cap + bottom) / 2 + height / 2 - cap
		placed = [(first - i * pitch, cap, middle, span) for i in range(len(lines))]
	layer = Image.new('L', (image.width * SS, image.height * SS))
	for text, (baseline, cap, middle, span) in zip(lines, placed):
		_draw_arc_line(layer, text, cx, cy, baseline, cap, middle, span)
	alpha = np.array(layer.resize((image.width, image.height), Image.LANCZOS)).astype(float) / 255
	shadow = np.roll(np.roll(alpha, dy, 0), dx, 1)
	image.target = over(over(clean, shadow_color, shadow), letter_color, alpha)
