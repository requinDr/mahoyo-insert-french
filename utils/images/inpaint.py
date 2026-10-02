"""Erasing the English text: rebuilding what is behind it.

The usual libraries (OpenCV inpaint, scikit-image inpaint_biharmonic) smooth the hole,
which erases the patterns of these images (dots, paper grid, plate lines). Here:
- the other language bands share the background, with their text placed elsewhere;
- a repeated pattern is continued with pieces of itself shifted by its period;
- lines and edges are continued across the hole.
"""
import numpy as np
from scipy import ndimage

from utils.images.game import GameImage


def text_masks(image: GameImage, value, sign: int, threshold: float, dilation: int,
               reference=np.median) -> list[np.ndarray]:
	"""Text (with its glow) of each band: where value(band) differs by more than threshold
	from reference(the other bands), brighter (sign = 1) or darker (sign = -1)."""
	values = [value(band) for band in image.bands]
	masks = []
	for i, own in enumerate(values):
		others = reference(np.stack([v for j, v in enumerate(values) if j != i]), axis=0)
		masks.append(ndimage.binary_dilation(ndimage.binary_opening((own - others) * sign > threshold),
		                                     iterations=dilation))
	return masks


def fill_from_bands(image: GameImage, masks: list[np.ndarray], hole: np.ndarray):
	"""Copy of the target band where the hole is filled from the other bands, wherever one of
	them has no text; and what is left of the hole."""
	clean, hole = image.target.copy(), hole.copy()
	for i, band in enumerate(image.bands):
		if i != image.target_band:
			usable = hole & ~masks[i]
			clean[usable] = band[usable]
			hole &= ~usable
	return clean, hole


def lattice_shifts(period_x: float, period_y: float, reach: int = 4, upward_only: bool = False):
	"""Translations (rows, columns) of a staggered pattern of dots (x, y periods between two
	neighbouring rows of dots), with a pixel of tolerance."""
	return [(round(period_y * b) + e, round(period_x * a) + f)
	        for a in range(-reach - 2, reach + 3) for b in range(-reach, 1 if upward_only else reach + 1)
	        if (a + b) % 2 == 0 and (a, b) != (0, 0) for e in (-1, 0, 1) for f in (-1, 0, 1)]


def grid_shifts(period: int, columns: int = 4, rows: int = 2):
	"""Translations by whole cells of a square grid."""
	return [(period * i, period * j) for i in range(-rows, rows + 1) for j in range(-columns, columns + 1) if (i, j) != (0, 0)]


def patch_fill(img: np.ndarray, hole: np.ndarray, shifts, block: int = 24):
	"""Fills the hole block by block with a shifted piece of the image, using the shift
	that best matches the block's surroundings. Returns the image and the blocks left."""
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


def diffuse(img: np.ndarray, hole: np.ndarray, iterations: int = 400) -> np.ndarray:
	"""Smooth fill, for plain areas (sky)."""
	ys, xs = np.nonzero(hole)
	y0, y1, x0, x1 = max(0, ys.min() - 20), ys.max() + 20, max(0, xs.min() - 20), xs.max() + 20
	out, mask = img.copy(), hole
	area, mask = out[y0:y1, x0:x1], mask[y0:y1, x0:x1]
	area[mask] = area[~mask].mean(0)
	for _ in range(iterations):
		area[mask] = ndimage.uniform_filter(area, (7, 7, 1))[mask]
	return out


def directional_fill(image: np.ndarray, hole: np.ndarray, reach: int = 80, horizontal_match: float = 30) -> np.ndarray:
	"""Fills each hole pixel by interpolating between the nearest known pixels on both sides.
	Horizontally when these two pixels are alike (difference of the RGB sum under
	horizontal_match: horizontal lines), otherwise along the direction (vertical or diagonal)
	where they are the most alike (edges)."""
	out = image.copy()
	height, width = hole.shape
	ys, xs = np.nonzero(hole)
	best = np.full(len(ys), np.inf)
	for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
		ends = []
		for sign in (1, -1):
			found = np.zeros(len(ys), bool)
			distance = np.full(len(ys), reach, float)
			value = np.zeros((len(ys), image.shape[2]))
			for step in range(1, reach):
				y, x = ys + sign * dy * step, xs + sign * dx * step
				inside = (y >= 0) & (y < height) & (x >= 0) & (x < width)
				y, x = np.clip(y, 0, height - 1), np.clip(x, 0, width - 1)
				hit = inside & ~hole[y, x] & ~found
				distance[hit] = step
				value[hit] = image[y[hit], x[hit]]
				found |= hit
			ends.append((found, distance, value))
		(found1, d1, v1), (found2, d2, v2) = ends
		mismatch = np.where(found1 & found2, np.abs(v1 - v2)[:, :3].sum(1), np.inf)
		if dy == 0:
			mismatch = np.where(mismatch < horizontal_match, -1.0, mismatch)
		better = mismatch < best
		best[better] = mismatch[better]
		blend = (v1 * d2[:, None] + v2 * d1[:, None]) / (d1 + d2)[:, None]
		out[ys[better], xs[better]] = blend[better]
	return out


def erase_text(image: GameImage, value, sign: int, threshold: float, dilation: int, shifts=None) -> np.ndarray:
	"""Target band without its text: background of the other bands (the most extreme of
	them, against the text: lightest under dark text), then the pattern (shifts) or a
	smooth fill where all the languages have text."""
	masks = text_masks(image, value, sign, threshold, dilation, reference=np.min if sign > 0 else np.max)
	clean, hole = fill_from_bands(image, masks, ndimage.binary_dilation(masks[image.target_band], iterations=3))
	if shifts and hole.any():
		clean, hole = patch_fill(clean, hole, shifts)
	if hole.any():
		clean = diffuse(clean, hole)
	return clean
