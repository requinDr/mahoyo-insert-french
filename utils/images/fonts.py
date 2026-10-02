"""Fonts used to draw text into images.

Fonts are not shipped with the project (licenses): they are searched in
sources/polices-images, then in the system font folders (Windows, Linux, macOS).
FONTS lists them by short name: a description and the file names to look for.
"""
import os
import sys
from functools import cache
from pathlib import Path

from PIL import ImageFont

PROJECT_FONTS = Path(__file__).resolve().parents[2] / 'sources' / 'polices-images'

FONTS = {
	'arial_rounded': ('Arial Rounded MT Bold', 'arlrdbd.ttf'),
	'helvetica': ('Helvetica Neue (Roman)', 'HelveticaNeueRoman.otf', 'HelveticaNeue-Roman.otf',
	              'helveticaneue-roman.ttf', 'HelveticaNeue.ttc', 'arial.ttf', 'Arial.ttf'),
	'helvetica_bold': ('Helvetica Neue (Bold)', 'HelveticaNeueBold.otf', 'HelveticaNeue-Bold.otf',
	                   'HelveticaNeue.ttc', 'arialbd.ttf', 'Arial Bold.ttf'),
	'palatino': ('Palatino Linotype', 'pala.ttf', 'Palatino Linotype.ttf', 'Palatino.ttc'),
	'segoe_print': ('Segoe Print', 'segoepr.ttf'),
	'segoe_print_bold': ('Segoe Print Bold', 'segoeprb.ttf'),
	'segoe_light': ('Segoe UI Light', 'segoeuil.ttf'),
	'segoe_light_italic': ('Segoe UI Light Italic', 'seguili.ttf'),
	'yu_mincho': ('Yu Mincho', 'yumin.ttf', 'YuMincho.ttc', 'NotoSerifJP-VF.ttf', 'NotoSerifCJK-Regular.ttc'),
}


def _font_dirs() -> list[Path]:
	dirs = [PROJECT_FONTS]
	home = Path.home()
	if sys.platform == 'win32':
		dirs += [Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Fonts',
		         Path(os.environ.get('LOCALAPPDATA', home / 'AppData' / 'Local')) / 'Microsoft' / 'Windows' / 'Fonts']
	elif sys.platform == 'darwin':
		dirs += [home / 'Library' / 'Fonts', Path('/Library/Fonts'), Path('/System/Library/Fonts')]
	else:
		dirs += [home / '.local' / 'share' / 'fonts', home / '.fonts', Path('/usr/local/share/fonts'), Path('/usr/share/fonts')]
	return [d for d in dirs if d.is_dir()]


@cache
def _index() -> dict[str, Path]:
	"""Font files by lowercase name (the first folder found wins)."""
	found: dict[str, Path] = {}
	for directory in _font_dirs():
		for path in directory.rglob('*'):
			if path.suffix.lower() in ('.ttf', '.otf', '.ttc'):
				found.setdefault(path.name.lower(), path)
	return found


@cache
def font_path(name: str) -> str:
	"""Path of the font FONTS[name]; otherwise an explicit error."""
	description, *file_names = FONTS[name]
	for file_name in file_names:
		path = _index().get(file_name.lower())
		if path:
			return str(path)
	raise FileNotFoundError(
		f"Police introuvable : {description} ({', '.join(file_names)}).\n"
		f"Installez-la, ou copiez le fichier dans {PROJECT_FONTS}.")


def load_font(name: str, size: float) -> ImageFont.FreeTypeFont:
	return ImageFont.truetype(font_path(name), round(size))


def size_for_height(name: str, height: float, char: str = 'H') -> float:
	"""Font size at which char is height pixels tall."""
	box = load_font(name, 100).getbbox(char)
	return height / ((box[3] - box[1]) / 100)
