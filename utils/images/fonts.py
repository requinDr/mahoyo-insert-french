"""Lookup of the fonts used to draw text into images.

Fonts are not shipped with the project (licenses): they are searched in
sources/polices-images, then in the system font folders (Windows, Linux, macOS).
"""
import os
import sys
from functools import cache
from pathlib import Path

PROJECT_FONTS = Path(__file__).resolve().parents[2] / 'sources' / 'polices-images'


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


def find_font(description: str, *file_names: str) -> str:
	"""Path of the first file found among file_names; otherwise an explicit error."""
	for name in file_names:
		path = _index().get(name.lower())
		if path:
			return str(path)
	raise FileNotFoundError(
		f"Police introuvable : {description} ({', '.join(file_names)}).\n"
		f"Installez-la, ou copiez le fichier dans {PROJECT_FONTS}.")
