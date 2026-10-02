"""Original game images, read directly from its archives."""
import numpy as np
from PIL import Image

import utils.config_importer as conf
from utils.steam.build_patch import ARCHIVE_NAME
from utils.steam.hfa import find_in_archives
from utils.steam.mzp import decode_mzp

# Images shared by all languages have 4 horizontal bands: ja, en, zc, zt.
# The patch replaces English: that is the band to redraw.
BANDS = 4
TARGET_BAND = 1


def original_image(number: int) -> Image.Image:
	name = f'img{number}.mzp'
	data = find_in_archives(conf.game_folder, name, exclude=ARCHIVE_NAME)
	if data is None:
		raise FileNotFoundError(f'{name} introuvable dans les archives du jeu ({conf.game_folder})')
	return decode_mzp(data)


def split_bands(image: Image.Image) -> tuple[np.ndarray, int]:
	"""RGBA pixels of the image and height of one band."""
	pixels = np.array(image.convert('RGBA'))
	return pixels, pixels.shape[0] // BANDS
