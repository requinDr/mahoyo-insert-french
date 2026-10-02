"""Chapter title cards (img0409 to img0422): "--- N ¦ Title ---" on a dashed line, with a
dashed vertical separator after the number. The left part of the English band (leading
dashes, number, separator) is kept as is; the English title is erased, the dashed line is
redrawn under the new title, and the title is written in the English style (white serif
with a soft dark shadow). The right edge of the card stays where the English one ends."""
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

from utils.images.fonts import find_font
from utils.images.game import TARGET_BAND, original_image, split_bands

SS = 3  # supersampling
MIN_LEFT = 40  # the card must not start closer to the left edge of the image


def _font_path():
	return find_font('Yu Mincho', 'yumin.ttf', 'YuMincho.ttc', 'NotoSerifJP-VF.ttf', 'NotoSerifCJK-Regular.ttc')


def _runs(values):
	"""Ranges of consecutive True values."""
	runs, start = [], None
	for i, value in enumerate(np.append(values, False)):
		if value and start is None:
			start = i
		elif not value and start is not None:
			runs.append((start, i))
			start = None
	return runs


def _layout(band):
	"""Measures the English card: dashed line rows, separator, number, title."""
	light = (band[..., 3] >= 100) & (band[..., :3].mean(-1) > 150)
	ys, xs = np.nonzero(light)
	left, right, top = xs.min(), xs.max(), ys.min()
	# the separator is the only thing above the letters
	separator = np.flatnonzero(light[top:top + 15].any(0))
	# the dashed line is the only thing at the far right (the card ends with dashes)
	dash_rows = np.flatnonzero(light[:, right - 25:right + 1].any(1))
	letters = light.copy()
	letters[dash_rows.min() - 1:dash_rows.max() + 2] = False
	letters[:, separator.min() - 1:separator.max() + 2] = False
	parts = _runs(letters.any(0))
	number = [p for p in parts if p[1] <= separator.min()]
	title = [p for p in parts if p[0] >= separator.max()]
	number_rows = np.flatnonzero(letters[:, number[0][0]:number[-1][1]].any(1))
	return dict(left=left, right=right, dash_rows=(dash_rows.min(), dash_rows.max() + 1),
	            number_start=number[0][0], separator_end=separator.max() + 1,
	            title_start=title[0][0], title_end=title[-1][1],
	            cap=number_rows[-1] - number_rows[0] + 1, baseline=number_rows[-1] + 1,
	            letters=letters, light=light)


def _cut_column(band, layout):
	"""Column between the separator and the English title where the card is cut: the one
	with the least shadow, so that no piece of the English title's shadow is kept."""
	y0, y1 = layout['dash_rows']
	shade = band[..., 3].copy()
	shade[layout['light']] = 0
	shade[y0 - 3:y1 + 3] = 0
	start, stop = layout['separator_end'] + 2, layout['title_start'] - 1
	return start + int(np.argmin(shade[:, start:stop].sum(0)))


def _over_image(base, top):
	"""Composites an RGBA float image over another one."""
	a = top[..., 3:] / 255
	base_alpha = base[..., 3:] / 255
	out_alpha = a + base_alpha * (1 - a)
	rgb = (top[..., :3] * a + base[..., :3] * base_alpha * (1 - a)) / np.maximum(out_alpha, 1e-6)
	return np.concatenate([rgb, out_alpha * 255], -1)


def _dash_period(band, layout):
	"""Spacing of the dashes, measured on the leading dashes."""
	y0, y1 = layout['dash_rows']
	row = (band[y0:y1, layout['left']:layout['number_start'], 3] > 100).any(0)
	starts = [a for a, _ in _runs(row)]
	return int(round(np.median(np.diff(starts)))) if len(starts) > 1 else 24, starts[0] + layout['left']


def _fit_shadow(band, letters):
	"""Soft shadow of the English letters as (blur radius, strength)."""
	core = letters.astype(float) * 255
	alpha = band[..., 3].astype(float)
	dark = band[..., :3].mean(-1) < 100
	around = dark & ~ndimage.binary_dilation(letters, iterations=1) & ndimage.binary_dilation(letters, iterations=12)
	best = None
	for sigma in np.arange(1.0, 8.0, 0.5):
		blurred = ndimage.gaussian_filter(core, sigma)
		strength = (alpha[around] * blurred[around]).sum() / max((blurred[around] ** 2).sum(), 1e-6)
		error = ((alpha[around] - strength * blurred[around]) ** 2).mean()
		if best is None or error < best[0]:
			best = (error, sigma, strength)
	return best[1], best[2]


def _letter_gap(mask, cap):
	gaps = [b - a for a, b in _runs(~mask.any(0)[np.flatnonzero(mask.any(0))[0]:])]
	gaps = [g for g in gaps if g < cap * 0.3]
	return float(np.median(gaps)) if gaps else 0.0


def _fit_tracking(text, font, gap_target, cap):
	"""Letter spacing (px at SS scale) giving the same gaps between letters as the English title."""
	best = None
	for tracking in np.arange(0, 0.2, 0.01) * font.size:
		mask, _ = _render(text, font, tracking)
		small = np.array(Image.fromarray(mask).resize((max(1, mask.shape[1] // SS), max(1, mask.shape[0] // SS)),
		                                              Image.LANCZOS)) > 128
		error = abs(_letter_gap(small, cap) - gap_target)
		if best is None or error < best[0]:
			best = (error, tracking)
	return best[1]


def _render(text, font, tracking):
	widths = [font.getlength(c) + tracking for c in text]
	image = Image.new('L', (int(sum(widths) + font.size * 2), int(font.size * 2)))
	draw = ImageDraw.Draw(image)
	x = font.size * 0.5
	for c, w in zip(text, widths):
		draw.text((x, font.size * 0.5), c, font=font, fill=255)
		x += w
	mask = np.array(image)
	xs = np.flatnonzero(mask.max(0) > 0)
	return mask[:, xs[0]:xs[-1] + 1], font.size * 0.5 + font.getmetrics()[0]


def _over(base, color, alpha):
	"""Composites a flat color with the given alpha (0-1) over an RGBA float image."""
	a = alpha[..., None]
	base_alpha = base[..., 3:] / 255
	out_alpha = a + base_alpha * (1 - a)
	rgb = (np.array(color) * a + base[..., :3] * base_alpha * (1 - a)) / np.maximum(out_alpha, 1e-6)
	return np.concatenate([rgb, out_alpha * 255], -1)


def generate(titles: dict, out_dir) -> list[str]:
	written = []
	font_path = _font_path()
	reference = ImageFont.truetype(font_path, 100)
	digit = reference.getbbox('1')
	for key, text in titles.items():
		number = int(key)
		pixels, height = split_bands(original_image(number))
		band = pixels[TARGET_BAND * height:(TARGET_BAND + 1) * height].astype(float)
		layout = _layout(band)
		english = layout['letters'][:, layout['title_start']:layout['title_end']]
		color = np.median(band[layout['letters']][:, :3], 0)
		sigma, strength = _fit_shadow(band, layout['letters'])
		size = layout['cap'] / ((digit[3] - digit[1]) / 100)  # digits as tall as the English ones
		gap_target = _letter_gap(english, layout['cap'])
		while True:
			font = ImageFont.truetype(font_path, round(size * SS))
			tracking = _fit_tracking(text, font, gap_target, layout['cap'])
			mask, offset = _render(text, font, tracking)
			shift = (layout['title_end'] - layout['title_start']) - mask.shape[1] / SS
			if layout['left'] + shift >= MIN_LEFT:
				break
			size *= 0.97
		shift = int(round(shift))

		# left part (leading dashes, number, separator) moved so that the right edge stays put
		width = band.shape[1]
		card = np.zeros_like(band)
		cut = _cut_column(band, layout)
		source = slice(max(0, -shift), cut)
		card[:, source.start + shift:cut + shift] = band[:, source]
		# title letters and their shadow
		layer = Image.new('L', (width * SS, height * SS))
		piece = Image.fromarray(mask)
		title_x = layout['title_start'] + shift
		layer.paste(piece, (int(round(title_x * SS)), int(round(layout['baseline'] * SS - offset))), piece)
		letters = np.array(layer.resize((width, height), Image.LANCZOS)).astype(float)
		shadow = np.clip(ndimage.gaussian_filter(letters, sigma) * strength / 255, 0, 1)
		# same stacking as the English card: shadow, then the dashed line, then the letters
		card = _over(card, (0, 0, 0), shadow)
		period, phase = _dash_period(band, layout)
		y0, y1 = layout['dash_rows'][0] - 3, layout['dash_rows'][1] + 3
		strip = band[y0:y1, phase:phase + period]
		x = phase + shift + period * int(np.ceil((cut - phase) / period))
		while x < layout['right'] + 1:
			w = min(period, layout['right'] + 1 - x)
			target = card[y0:y1, x:x + w]
			card[y0:y1, x:x + w] = _over_image(target, strip[:, :w])
			x += period
		card = _over(card, color, letters / 255)

		pixels[TARGET_BAND * height:(TARGET_BAND + 1) * height] = np.clip(np.round(card), 0, 255).astype(np.uint8)
		Image.fromarray(pixels).save(out_dir / f'img{number:04d}.png', optimize=True)
		written.append(f'img{number:04d}.png')
	return written
