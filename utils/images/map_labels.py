"""Labels of the mansion maps (img1372 to img1379, img2393 to img2395): room names
("Entrance Corridor", "Foyer") and floor names ("2F", "1F", "B1", italic), thin white
letters with a light blue glow, sometimes dimmed when the map highlights another part.

- Room names differ between the language bands: the English one is erased with the
  background of the other bands, then the dot pattern fills what is left.
- Floor names are the same in every band: they are found by their brightness and erased
  with shifted pieces of the plate around them (its lines are horizontal).
The new labels keep the English size, position (same center and baseline), glow and dimming.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

from utils.images.fonts import find_font
from utils.images.game import BANDS, TARGET_BAND, original_image, split_bands
from utils.images.text_backgrounds import _patch_fill

SS = 3                 # supersampling
FULL_GLOW = 245        # brightness gain of a label that is not dimmed
FLOOR_GLYPH = (55, 90)  # height range of the floor name glyphs (px)
FLOOR_WIDTH = 140       # minimum width of a floor name with its merging margin (px)
FLOOR_PRESENT = 40      # brightness above the plate of a floor name, even dimmed
HORIZONTAL_MATCH = 30   # max difference (sum of RGB) to fill along the plate lines
ROOM_AREA = 4000       # smaller differences between the bands are not room names
# translations of the dot pattern of the background (rows, columns), measured on img1376;
# only upward, away from the plates under the labels
DOT_SHIFTS = [(round(18.75 * b) + e, round(19.35 * a) + f)
              for a in range(-6, 7) for b in range(-4, 1) if (a + b) % 2 == 0 and (a, b) != (0, 0)
              for e in (-1, 0, 1) for f in (-1, 0, 1)]


def _font_path(italic):
	if italic:
		return find_font('Segoe UI Light Italic', 'seguili.ttf', 'SEGUILI.TTF')
	return find_font('Segoe UI Light', 'segoeuil.ttf', 'SEGOEUIL.TTF')


def _brightness(pixels):
	"""Premultiplied brightness of the darkest of red and green (white text stands out
	from the blue background)."""
	return np.minimum(pixels[..., 0], pixels[..., 1]) * pixels[..., 3] / 255


def _groups(mask, gap):
	"""Bounding boxes (row slice, column slice) of the parts of mask, merged when closer than gap."""
	labels, _ = ndimage.label(ndimage.binary_dilation(mask, iterations=gap))
	return [box for box in ndimage.find_objects(labels)]


def _room_masks(bands):
	"""Text of each band (with its glow): brighter than the other bands."""
	light = np.stack([_brightness(b) for b in bands])
	masks = []
	for i in range(BANDS):
		# median: where another language has a stroke at the same place, the text is still found
		others = np.median(np.stack([light[j] for j in range(BANDS) if j != i]), 0)
		masks.append(ndimage.binary_dilation(ndimage.binary_opening(light[i] - others > 12), iterations=10))
	return masks


def _directional_fill(image, hole, reach=80):
	"""Fills each hole pixel by interpolating between the nearest known pixels on both sides.
	Horizontally when these two pixels are alike (the plate lines are horizontal), otherwise
	along the direction where they are the most alike (the edges of the lighter bands)."""
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
		valid = found1 & found2
		mismatch = np.where(valid, np.abs(v1 - v2)[:, :3].sum(1), np.inf)
		if dx == 1 and dy == 0:
			mismatch = np.where(mismatch < HORIZONTAL_MATCH, -1.0, mismatch)
		better = mismatch < best
		best[better] = mismatch[better]
		blend = (v1 * d2[:, None] + v2 * d1[:, None]) / (d1 + d2)[:, None]
		out[ys[better], xs[better]] = blend[better]
	return out


def _floor_residual(band):
	"""Brightness above the local background (thin bright shapes: letters, plate lines)."""
	light = _brightness(band)
	return light - ndimage.median_filter(light, size=31)


def _floor_boxes(config):
	"""Boxes of the floor names, top to bottom, measured on the map that shows them all:
	glyphs about as tall as a capital, two per name."""
	number = int(max(config, key=lambda key: len(config[key].get('floors', []))))
	pixels, height = split_bands(original_image(number))
	residual = _floor_residual(pixels[TARGET_BAND * height:(TARGET_BAND + 1) * height].astype(float))
	labels, _ = ndimage.label(ndimage.binary_dilation(residual > 30, iterations=2))
	glyphs = np.zeros(residual.shape, bool)
	for i, box in enumerate(ndimage.find_objects(labels), 1):
		h, w = box[0].stop - box[0].start, box[1].stop - box[1].start
		if FLOOR_GLYPH[0] <= h <= FLOOR_GLYPH[1] and w <= 90:
			glyphs[box] |= labels[box] == i
	boxes = [box for box in _groups(glyphs, 25) if box[1].stop - box[1].start >= FLOOR_WIDTH]
	return sorted(boxes, key=lambda box: box[0].start)


def _measure(original, clean, box):
	"""Cap height, baseline, horizontal center, dimming of a label, from its brightest pixels.
	The height and baseline come from the first letter, a capital (descenders left out)."""
	gain = _brightness(original[box]) - _brightness(clean[box])
	core = gain > gain.max() * 0.6
	cols = np.flatnonzero(core.any(0))
	first = cols[0] + np.flatnonzero(~core[:, cols[0]:].any(0))[0]
	rows = np.flatnonzero(core[:, cols[0]:first].any(1))
	return dict(cap=rows[-1] - rows[0] + 1, baseline=box[0].start + rows[-1] + 1,
	            center=box[1].start + (cols[0] + cols[-1] + 1) / 2, dim=min(1.0, gain.max() / FULL_GLOW))


def _glow_model(config):
	"""Glow of the labels as (blur radius, strength, color), measured on a map part drawn on
	a transparent layer: there the glow is alone, its opacity is the alpha channel.
	Its opacity is about strength × blur(letters)."""
	for key, texts in config.items():
		pixels, height = split_bands(original_image(int(key)))
		band = pixels[TARGET_BAND * height:(TARGET_BAND + 1) * height].astype(float)
		alpha = band[..., 3] / 255
		letters = (alpha > 0.95) & (band[..., :3].min(-1) > 200)
		opaque_plate = (alpha > 0.95) & ~letters
		if texts.get('rooms') and letters.sum() > 500 and opaque_plate.mean() < 0.5:
			break
	else:
		raise ValueError('aucun plan sur fond transparent pour mesurer le halo')
	core = letters.astype(float)
	around = (ndimage.binary_dilation(letters, iterations=12) & ~ndimage.binary_dilation(letters, iterations=1)
	          & ~ndimage.binary_dilation(opaque_plate, iterations=2))
	best = None
	for sigma in np.arange(1.0, 10.0, 0.5):
		blurred = ndimage.gaussian_filter(core, sigma)
		strength = (alpha[around] * blurred[around]).sum() / max((blurred[around] ** 2).sum(), 1e-6)
		error = ((alpha[around] - strength * blurred[around]) ** 2).mean()
		if best is None or error < best[0]:
			best = (error, sigma, strength)
	color = np.median(band[around & (alpha > 0.05)][:, :3], 0)
	return best[1], best[2], color


def _render(text, italic, cap):
	font_path = _font_path(italic)
	reference = ImageFont.truetype(font_path, 100)
	box = reference.getbbox('H')
	font = ImageFont.truetype(font_path, round(cap / ((box[3] - box[1]) / 100) * SS))
	image = Image.new('L', (int(font.getlength(text) + font.size * 2), font.size * 2))
	ImageDraw.Draw(image).text((font.size * 0.5, font.size * 0.5), text, font=font, fill=255)
	mask = np.array(image)
	cols = np.flatnonzero(mask.max(0) > 0)
	return mask[:, cols[0]:cols[-1] + 1], font.size * 0.5 + font.getmetrics()[0]


def _over(base, color, alpha):
	a = alpha[..., None]
	base_alpha = base[..., 3:] / 255
	out_alpha = a + base_alpha * (1 - a)
	rgb = (np.asarray(color) * a + base[..., :3] * base_alpha * (1 - a)) / np.maximum(out_alpha, 1e-6)
	return np.concatenate([rgb, out_alpha * 255], -1)


def generate(config: dict, out_dir) -> list[str]:
	written = []
	floor_boxes = _floor_boxes(config)
	sigma, strength, glow_color = _glow_model(config)
	for key, texts in config.items():
		number = int(key)
		pixels, height = split_bands(original_image(number))
		pixels = pixels.astype(float)
		bands = [pixels[i * height:(i + 1) * height] for i in range(BANDS)]
		original = bands[TARGET_BAND]
		clean = original.copy()
		labels = []

		# room names: background of the other bands, then the dot pattern
		masks = _room_masks(bands)
		rooms = [box for box in _groups(masks[TARGET_BAND], 4)
		         if masks[TARGET_BAND][box].sum() > ROOM_AREA]
		rooms.sort(key=lambda box: box[1].start)
		if len(rooms) != len(texts.get('rooms', [])):
			raise ValueError(f'img{number:04d} : {len(rooms)} noms de pièce dans l\'image, '
			                 f'{len(texts.get("rooms", []))} dans le JSON')
		# only the room names: the bands also differ slightly elsewhere on some maps
		hole = np.zeros_like(masks[TARGET_BAND])
		bright = _floor_residual(original) > 20
		for box in rooms:
			hole[box] = masks[TARGET_BAND][box]
			# small bright bits left in the box (strokes shared with another language)
			parts, count = ndimage.label(bright[box])
			sizes = ndimage.sum(np.ones_like(parts), parts, range(1, count + 1))
			small = np.isin(parts, 1 + np.flatnonzero(sizes < 400)) & (parts > 0)
			hole[box] |= ndimage.binary_dilation(small, iterations=4)
		# on a transparent layer (map parts drawn separately) nothing is behind the text but
		# the plates: everything else under the English label becomes fully transparent
		ring = ndimage.binary_dilation(hole, iterations=6) & ~hole
		transparent = clean[ring][:, 3].mean() < 128 if hole.any() else False
		if transparent:
			for i in range(BANDS):
				if i != TARGET_BAND:
					usable = hole & ~masks[i]
					clean[usable] = bands[i][usable]
					hole &= ~usable
			region = np.zeros_like(hole)
			for box in rooms:
				region[box] = masks[TARGET_BAND][box]
			faint = region & (clean[..., 3] < 200)
			clean[faint | hole] = 0
		elif hole.any():
			# on a full map the other bands may differ around the label (highlighted parts):
			# the dot pattern alone fills the hole
			clean, left = _patch_fill(clean, hole, DOT_SHIFTS)
			# blocks with no usable piece of the pattern nearby, and pieces that brought a bit
			# of a plate (brighter than anything around the label)
			level = clean[..., :3].mean(-1)
			ring = ndimage.binary_dilation(hole, iterations=8) & ~hole
			left |= hole & (level > np.percentile(level[ring], 98) + 10)
			if left.any():
				clean = _directional_fill(clean, ndimage.binary_dilation(left, iterations=2) & hole)
		labels += [dict(box=box, text=text, italic=False) for box, text in zip(rooms, texts.get('rooms', []))]

		# floor names: same in every band, at the same place in every map; erased with
		# the plate around them
		residual = _floor_residual(original)
		floors = [box for box in floor_boxes if residual[box].max() > FLOOR_PRESENT]
		if len(floors) != len(texts.get('floors', [])):
			raise ValueError(f'img{number:04d} : {len(floors)} noms d\'étage dans l\'image, '
			                 f'{len(texts.get("floors", []))} dans le JSON')
		for box in floors:
			hole = np.zeros(residual.shape, bool)
			hole[box] = ndimage.binary_dilation(residual[box] > residual[box].max() * 0.3, iterations=8)
			clean = _directional_fill(clean, hole)
		labels += [dict(box=box, text=text, italic=True) for box, text in zip(floors, texts.get('floors', []))]

		for label in labels:
			label.update(_measure(original, clean, label['box']))

		width = clean.shape[1]
		result = clean
		for label in labels:
			mask, offset = _render(label['text'], label['italic'], label['cap'])
			layer = Image.new('L', (width * SS, height * SS))
			x = label['center'] * SS - mask.shape[1] / 2
			layer.paste(Image.fromarray(mask), (int(round(x)), int(round(label['baseline'] * SS - offset))))
			letters = np.array(layer.resize((width, height), Image.LANCZOS)).astype(float) / 255
			# blurred from the letters' body, like the measure on the English letters
			glow = np.clip(ndimage.gaussian_filter((letters > 0.5).astype(float), sigma) * strength, 0, 1)
			result = _over(result, glow_color, glow * label['dim'])
			result = _over(result, (255, 255, 255), letters * label['dim'])

		pixels[TARGET_BAND * height:(TARGET_BAND + 1) * height] = result
		Image.fromarray(np.clip(np.round(pixels), 0, 255).astype(np.uint8)).save(out_dir / f'img{number:04d}.png', optimize=True)
		written.append(f'img{number:04d}.png')
	return written
