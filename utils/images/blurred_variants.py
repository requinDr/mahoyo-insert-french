"""Blurred variants of the game images (name_NN_MM.mzp), drawn by the engine for some effects
(a logo projected on a screen, a title fading out…). Each one is the image moved by MARGIN
pixels to the right and down, then blurred with a box of radius 2×NN horizontally and 2×MM
vertically; the colors are averaged weighted by their opacity. They are generated with their
image (generate_images.py)."""
import re

import numpy as np
from PIL import Image
from scipy import ndimage

MARGIN = 15
VARIANT = re.compile(r"^(?P<base>.+)_(?P<x>\d\d)_(?P<y>\d\d)\.mzp$")


def blurred(image: Image.Image, x: int, y: int) -> Image.Image:
	pixels = np.array(image.convert("RGBA")).astype(float)
	moved = np.zeros_like(pixels)
	moved[MARGIN:, MARGIN:] = pixels[:-MARGIN, :-MARGIN]
	moved[..., :3] *= moved[..., 3:] / 255
	size = (2 * (2 * y) + 1, 2 * (2 * x) + 1)
	blur = np.stack([ndimage.uniform_filter(moved[..., c], size, mode="constant") for c in range(4)], -1)
	alpha = blur[..., 3:]
	blur[..., :3] = np.where(alpha > 0, blur[..., :3] * 255 / np.maximum(alpha, 1e-6), 0)
	return Image.fromarray(np.clip(np.round(blur), 0, 255).astype(np.uint8))


def variants_of(stem: str, names) -> list[tuple[str, int, int]]:
	"""Blurred variants (stem, x, y) of the image `stem` (e.g. img2174) among the resource `names`."""
	found = []
	for name in names:
		match = VARIANT.match(name)
		if match and match["base"] == stem:
			found.append((name[:-len(".mzp")], int(match["x"]), int(match["y"])))
	return sorted(found)
