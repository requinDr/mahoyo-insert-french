"""Lesson titles of "Why Ploy?" (img2167 to img2172): big rounded red letters on one
line, in place of and in the style of the English title."""
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from utils.images.fonts import find_font
from utils.images.game import TARGET_BAND, original_image, split_bands

COLOR = (189, 0, 0)
MAX_WIDTH = 1866       # width of the English lines that fill the band
CENTER = 940           # horizontal center of the English lines
MIN_SCALE_X = 0.9      # horizontal squeeze allowed before reducing the size
SS = 4                 # supersampling


def _font_path():
	return find_font('Arial Rounded MT Bold', 'arlrdbd.ttf', 'ARLRDBD.TTF')


def _digit_box(alpha):
	"""Top and bottom of the leading digit (the bottom is the baseline)."""
	cols = alpha.max(0) > 128
	x0 = np.flatnonzero(cols)[0]
	x1 = x0 + np.flatnonzero(~cols[x0:])[0]
	rows = np.flatnonzero(alpha[:, x0:x1].max(1) > 128)
	return rows[0], rows[-1] + 1


def _render(text, size):
	"""Text as a mask, stroke thickened like the English, thin space before ! and ?."""
	font = ImageFont.truetype(_font_path(), size)
	stroke = round(size * 0.018)
	pieces, x = [], 0.0
	for i, c in enumerate(text):
		if c == ' ' and i + 1 < len(text) and text[i + 1] in '!?':
			x += font.getlength(' ') * 0.5
			continue
		pieces.append((x, c))
		x += font.getlength(c)
		if i + 1 < len(text) and text[i + 1] != ' ':
			x += font.getlength(c + text[i + 1]) - font.getlength(c) - font.getlength(text[i + 1])  # kerning
	image = Image.new('L', (int(x + size * 2), size * 3), 0)
	draw = ImageDraw.Draw(image)
	for px, c in pieces:
		draw.text((px + size, size), c, font=font, fill=255, stroke_width=stroke, stroke_fill=255)
	return np.array(image)


def generate(texts: dict, out_dir) -> list[str]:
	written = []
	for key, text in texts.items():
		number = int(key)
		image, height = split_bands(original_image(number))
		band = image[TARGET_BAND * height:(TARGET_BAND + 1) * height]
		top, base = _digit_box(band[:, :, 3])
		# size at which the digit is as tall as the original digit
		mask = _render(text, 100 * SS)
		t, b = _digit_box(mask)
		scale = (base - top) / ((b - t) / SS) / SS
		cols = np.flatnonzero(mask.max(0) > 0)
		width = (cols[-1] - cols[0] + 1) * scale
		original = np.flatnonzero(band[:, :, 3].max(0) > 128)
		max_width = min(MAX_WIDTH, original[-1] - original[0] + 1)  # no wider than the original
		scale_x = scale * min(1.0, max_width / width)
		if scale_x < scale * MIN_SCALE_X:
			scale = scale_x / MIN_SCALE_X
		crop = Image.fromarray(mask[:, cols[0]:cols[-1] + 1])
		w, h = round(crop.width * scale_x), round(crop.height * scale)
		small = np.array(crop.resize((w, h), Image.LANCZOS)).astype(np.float32)
		# digit baseline on the original one, shared horizontal center
		y0, x0 = round(base - b * scale), round(CENTER - w / 2)
		alpha = np.zeros(band.shape[:2], np.float32)
		ys, xs = max(0, y0), max(0, x0)
		alpha[ys:y0 + h, xs:x0 + w] = small[ys - y0:min(h, band.shape[0] - y0), xs - x0:min(w, band.shape[1] - x0)]
		alpha = np.clip(alpha, 0, 255).astype(np.uint8)
		new_band = np.zeros_like(band)
		new_band[:, :, :3] = COLOR
		new_band[:, :, 3] = alpha
		new_band[alpha == 0] = 0
		image[TARGET_BAND * height:(TARGET_BAND + 1) * height] = new_band
		Image.fromarray(image).save(out_dir / f'img{number:04d}.png', optimize=True)
		written.append(f'img{number:04d}.png')
	return written
