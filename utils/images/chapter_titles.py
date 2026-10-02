"""Chapter title cards (img0409 to img0422): "--- N ¦ Title ---" on a dashed line, with a
dashed vertical separator after the number. The left part of the English card (leading
dashes, number, separator) is kept and moved so that the card still ends where the
English one ends; the dashed line is redrawn under the new title, written in the English
style (white serif with a soft dark shadow)."""
import numpy as np

from utils.images.effects import blur, fit_blur, over, over_image, ring
from utils.images.fonts import load_font, size_for_height
from utils.images.game import GameImage
from utils.images.text import SS, TextLayer, fit_tracking, render_line, runs

MIN_LEFT = 40  # the card must not start closer to the left edge of the image


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
	parts = runs(letters.any(0))
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


def _dash_period(band, layout):
	"""Spacing and first column of the dashes, measured on the leading dashes."""
	y0, y1 = layout['dash_rows']
	starts = [a for a, _ in runs((band[y0:y1, layout['left']:layout['number_start'], 3] > 100).any(0))]
	return int(round(np.median(np.diff(starts)))) if len(starts) > 1 else 24, starts[0] + layout['left']


def chapter_title(image: GameImage, text: str):
	band = image.target
	layout = _layout(band)
	english = layout['letters'][:, layout['title_start']:layout['title_end']]
	size = size_for_height('yu_mincho', layout['cap'], '1')  # digits as tall as the English ones
	while True:
		font = load_font('yu_mincho', size * SS)
		mask, offset = render_line(text, font, fit_tracking(text, font, english, layout['cap'], 0, 0.2))
		shift = (layout['title_end'] - layout['title_start']) - mask.shape[1] / SS
		if layout['left'] + shift >= MIN_LEFT:
			break
		size *= 0.97
	shift = int(round(shift))

	# left part (leading dashes, number, separator), moved
	card = np.zeros_like(band)
	cut = _cut_column(band, layout)
	start = max(0, -shift)
	card[:, start + shift:cut + shift] = band[:, start:cut]
	# title letters and their shadow
	layer = TextLayer(image.width, image.height)
	layer.paste(mask, offset, layout['title_start'] + shift, layout['baseline'])
	letters = layer.alpha()
	dark_around = (band[..., :3].mean(-1) < 100) & ring(layout['letters'], 1, 12)
	shadow = blur(letters, *fit_blur(layout['letters'], band[..., 3] / 255, dark_around, np.arange(1.0, 8.0, 0.5)))
	# same stacking as the English card: shadow, then the dashed line, then the letters
	card = over(card, (0, 0, 0), shadow)
	period, phase = _dash_period(band, layout)
	y0, y1 = layout['dash_rows'][0] - 3, layout['dash_rows'][1] + 3
	strip = band[y0:y1, phase:phase + period]
	for x in range(phase + shift + period * int(np.ceil((cut - phase) / period)), layout['right'] + 1, period):
		w = min(period, layout['right'] + 1 - x)
		card[y0:y1, x:x + w] = over_image(card[y0:y1, x:x + w], strip[:, :w])
	image.target = over(card, np.median(band[layout['letters']][:, :3], 0), letters)
