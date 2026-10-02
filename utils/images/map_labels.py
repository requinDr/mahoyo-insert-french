"""Labels of the mansion maps (img1372 to img1379, img2393 to img2395): room names
("Entrance Corridor", "Foyer") and floor names ("2F", "1F", "B1", italic), thin white
letters with a light cyan glow, dimmed when the map highlights another part.

- Room names differ between the language bands. On a part drawn on a transparent layer
  (img1372, img1373) the English one is just removed; on a full map, the dot pattern of
  the background is continued over it.
- Floor names are the same in every band and at the same place on every map: they are
  erased by continuing the plate under them (its lines are horizontal).
The new labels keep the English size, position (same center and baseline) and dimming.
"""
from functools import cache

import numpy as np
from scipy import ndimage

from utils.images.effects import blur, fit_blur, over, ring
from utils.images.fonts import load_font, size_for_height
from utils.images.game import GameImage
from utils.images.inpaint import directional_fill, fill_from_bands, lattice_shifts, patch_fill, text_masks
from utils.images.text import SS, TextLayer, first_letter, render_line

FULL_MAP = '1378'       # map showing every floor name, where they are located
LAYER_PART = '1372'     # map part on a transparent layer, where the glow is measured
FULL_GLOW = 245        # brightness gain of a label that is not dimmed
FLOOR_GLYPH = (55, 90)  # height range of the floor name glyphs (px)
FLOOR_WIDTH = 140      # minimum width of a floor name with its merging margin (px)
FLOOR_PRESENT = 40     # brightness above the plate of a floor name, even dimmed
ROOM_AREA = 4000       # smaller differences between the bands are not room names
# dot pattern of the background (measured on img1376), only upward: away from the plates
DOT_SHIFTS = lattice_shifts(19.35, 18.75, upward_only=True)


def _brightness(band):
	"""Premultiplied brightness of the darkest of red and green (white text stands out
	from the blue background)."""
	return np.minimum(band[..., 0], band[..., 1]) * band[..., 3] / 255


def _residual(band):
	"""Brightness above the local background (thin bright shapes: letters, plate lines)."""
	light = _brightness(band)
	return light - ndimage.median_filter(light, size=31)


def _groups(mask, gap):
	"""Bounding boxes of the parts of mask, merged when closer than gap."""
	return ndimage.find_objects(ndimage.label(ndimage.binary_dilation(mask, iterations=gap))[0])


@cache
def _floor_boxes():
	"""Boxes of the floor names, top to bottom: glyphs about as tall as a capital, two per name."""
	residual = _residual(GameImage(FULL_MAP).target)
	labels, _ = ndimage.label(ndimage.binary_dilation(residual > 30, iterations=2))
	glyphs = np.zeros(residual.shape, bool)
	for i, box in enumerate(ndimage.find_objects(labels), 1):
		h, w = box[0].stop - box[0].start, box[1].stop - box[1].start
		if FLOOR_GLYPH[0] <= h <= FLOOR_GLYPH[1] and w <= 90:
			glyphs[box] |= labels[box] == i
	boxes = [box for box in _groups(glyphs, 25) if box[1].stop - box[1].start >= FLOOR_WIDTH]
	return sorted(boxes, key=lambda box: box[0].start)


@cache
def _glow():
	"""(sigma, strength, color) of the glow, where it is alone: its opacity is the alpha channel."""
	band = GameImage(LAYER_PART).target
	alpha = band[..., 3] / 255
	letters = (alpha > 0.95) & (band[..., :3].min(-1) > 200)
	plates = (alpha > 0.95) & ~letters
	around = ring(letters, 1, 12) & ~ndimage.binary_dilation(plates, iterations=2)
	sigma, strength = fit_blur(letters, alpha, around, np.arange(1.0, 10.0, 0.5))
	return sigma, strength, np.median(band[around & (alpha > 0.05)][:, :3], 0)


def _erase_rooms(image, count):
	"""Target band without its room names, and their boxes (left to right)."""
	masks = text_masks(image, _brightness, 1, 12, 10)
	rooms = sorted((box for box in _groups(masks[image.target_band], 4) if masks[image.target_band][box].sum() > ROOM_AREA),
	               key=lambda box: box[1].start)
	if len(rooms) != count:
		raise ValueError(f'{image.name} : {len(rooms)} noms de pièce dans l\'image, {count} dans le JSON')
	hole = np.zeros_like(masks[image.target_band])
	bright = _residual(image.target) > 20
	for box in rooms:
		hole[box] = masks[image.target_band][box]
		# small bright bits left in the box (strokes shared with another language)
		parts, n = ndimage.label(bright[box])
		small = np.isin(parts, 1 + np.flatnonzero(ndimage.sum(np.ones_like(parts), parts, range(1, n + 1)) < 400))
		hole[box] |= ndimage.binary_dilation(small & (parts > 0), iterations=4)
	clean = image.target.copy()
	if not hole.any():
		return clean, rooms
	if clean[ring(hole, 0, 6)][:, 3].mean() < 128:
		# transparent layer: only the plates are kept, from the other bands where needed
		region = hole.copy()
		clean, hole = fill_from_bands(image, masks, hole)
		clean[(region & (clean[..., 3] < 200)) | hole] = 0
	else:
		# full map: the other bands may differ around the label (highlighted parts), the dot
		# pattern alone fills it; what it cannot fill, and pieces that brought a bit of a
		# plate (brighter than anything around the label), are filled along lines and edges
		clean, left = patch_fill(clean, hole, DOT_SHIFTS)
		level = clean[..., :3].mean(-1)
		left |= hole & (level > np.percentile(level[ring(hole, 0, 8)], 98) + 10)
		if left.any():
			clean = directional_fill(clean, ndimage.binary_dilation(left, iterations=2) & hole)
	return clean, rooms


def _erase_floors(image, clean, count):
	residual = _residual(image.target)
	floors = [box for box in _floor_boxes() if residual[box].max() > FLOOR_PRESENT]
	if len(floors) != count:
		raise ValueError(f'{image.name} : {len(floors)} noms d\'étage dans l\'image, {count} dans le JSON')
	for box in floors:
		hole = np.zeros(residual.shape, bool)
		hole[box] = ndimage.binary_dilation(residual[box] > residual[box].max() * 0.3, iterations=8)
		clean = directional_fill(clean, hole)
	return clean, floors


def map_labels(image: GameImage, texts: dict):
	"""texts: room names left to right ('rooms'), floor names top to bottom ('floors')."""
	original = image.target
	clean, rooms = _erase_rooms(image, len(texts.get('rooms', [])))
	clean, floors = _erase_floors(image, clean, len(texts.get('floors', [])))
	sigma, strength, glow_color = _glow()
	result = clean
	for box, text, font_name in ([(box, text, 'segoe_light') for box, text in zip(rooms, texts.get('rooms', []))] +
	                             [(box, text, 'segoe_light_italic') for box, text in zip(floors, texts.get('floors', []))]):
		# size, position and dimming of the English label, from its brightest pixels
		gain = _brightness(original[box]) - _brightness(clean[box])
		core = gain > gain.max() * 0.6
		cap, baseline = first_letter(core)
		cols = np.flatnonzero(core.any(0))
		dim = min(1.0, gain.max() / FULL_GLOW)
		layer = TextLayer(image.width, image.height)
		layer.paste_centered(*render_line(text, load_font(font_name, size_for_height(font_name, cap) * SS)),
		                     box[1].start + (cols[0] + cols[-1] + 1) / 2, box[0].start + baseline)
		letters = layer.alpha()
		result = over(result, glow_color, blur(letters, sigma, strength) * dim)
		result = over(result, (255, 255, 255), letters * dim)
	image.target = result
