"""Original game images, read directly from its archives.

Two kinds of images:
- shared by all languages (imgNNNN.mzp named by their number, or name.mzp named by name):
  4 horizontal bands ja, en, zc, zt; the patch redraws the English one;
- English images (name_en.cbg, named by name): the whole image is redrawn, saved as name_fr.
"""
from pathlib import Path

import numpy as np
from PIL import Image

import utils.config_importer as conf
from utils.steam.build_patch import ARCHIVE_NAME
from utils.steam.cbg import decode_cbg
from utils.steam.hfa import find_in_archives
from utils.steam.mzp import decode_mzp

BANDS = 4        # bands of the images shared by all languages
TARGET_BAND = 1  # the English band, redrawn


def _find(name: str) -> bytes | None:
	return find_in_archives(conf.game_folder, name, exclude=ARCHIVE_NAME)


def _read(name: str) -> bytes:
	data = _find(name)
	if data is None:
		raise FileNotFoundError(f'{name} introuvable dans les archives du jeu ({conf.game_folder})')
	return data


def original_image(number: int) -> Image.Image:
	return decode_mzp(_read(f'img{number:04d}.mzp'))


class GameImage:
	"""A game image as float RGBA pixels. An edit redraws `target` (the English band, or the
	whole English image); the other bands are left as they are."""

	def __init__(self, key: str):
		"""key: number or name of an image shared by all languages, or name of an English image."""
		self.number = int(key) if key.isdigit() else None
		self.name = f'img{self.number:04d}' if self.number is not None else key
		english = None if self.number is not None else _find(f'{key}_en.cbg')
		self.shared = english is None
		image = decode_cbg(english) if english else decode_mzp(_read(f'{self.name}.mzp'))
		self.pixels = np.array(image.convert('RGBA')).astype(float)
		self.band_count = BANDS if self.shared else 1
		self.target_band = TARGET_BAND if self.shared else 0
		self.height = self.pixels.shape[0] // self.band_count
		self.width = self.pixels.shape[1]

	def band(self, index: int) -> np.ndarray:
		return self.pixels[index * self.height:(index + 1) * self.height]

	@property
	def bands(self) -> list[np.ndarray]:
		return [self.band(i) for i in range(self.band_count)]

	@property
	def target(self) -> np.ndarray:
		return self.band(self.target_band)

	@target.setter
	def target(self, value: np.ndarray):
		self.pixels[self.target_band * self.height:(self.target_band + 1) * self.height] = value

	def ink_bounds(self, alpha: float) -> tuple[int, int]:
		"""Right and bottom edges of the area used by the text of all the languages."""
		masks = [band[..., 3] > alpha for band in self.bands]
		return (max(np.flatnonzero(m.any(0))[-1] for m in masks),
		        max(np.flatnonzero(m.any(1))[-1] for m in masks))

	@property
	def file_name(self) -> str:
		return f'{self.name}.png' if self.shared else f'{self.name}_fr.png'

	def save(self, out_dir: Path):
		Image.fromarray(np.clip(np.round(self.pixels), 0, 255).astype(np.uint8)).save(out_dir / self.file_name, optimize=True)
