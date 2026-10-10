"""Builds the Steam patch: version.dll + data00999.hfa, to copy into the game folder."""
import csv
import io
import re
import shutil
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from PIL import Image

from utils.steam import line_breaks
from utils.steam.cbg import encode_cbg
from utils.steam.hfa import find_in_archives, read_hfa, write_hfa
from utils.steam.menu_cursors import DATA_PATCHES_ENTRY, data_patches
from utils.steam.mzp import decode_mzp, encode_mzp_delta

ARCHIVE_NAME = "data00999.hfa"
DLL_NAME = "version.dll"
TEXT5_ENTRY = "TEXT5_fr.csv"  # name expected by native/version.c
# Steam archives holding the images, fonts and texts specific to English
ENGLISH_ARCHIVES = ("data00000.hfa", "data00100.hfa")
# An image shared by all languages is made of horizontal bands ja, en, zc, zt; its PNG holds
# only the English band, redrawn
LANGUAGE_BANDS = 4
ENGLISH_BAND = 1
# Built from native/version.c (see native/build_dll.py)
DLL_PATH = Path(__file__).resolve().parents[2] / "native" / "version.dll"

# Resources shared by all languages: same table as shared_names in native/version.c
SHARED_NAMES = {"mode1.cbg": "modfr.cbg"}


def french_name(name: str) -> str | None:
	"""Same rule as french_name() in native/version.c."""
	if name in SHARED_NAMES:
		return SHARED_NAMES[name]
	new = re.sub(r"_en(?=[_.])", "_fr", name)
	if new.startswith("Font010"):
		new = "Font040" + new[7:]
	return new if new != name else None


def _encode_image(path: Path, name: str, game_dir: str) -> bytes:
	"""PNG converted to the game format: .cbg for an English resource; for an image shared
	by all languages (PNG of its English band, or of the whole image when it is not made of
	language bands), delta of the original .mzp (its changed tiles), which version.dll applies
	to the original read from the game archive."""
	with Image.open(path) as image:
		if name.endswith(".cbg"):
			return encode_cbg(image)
		original = find_in_archives(game_dir, path.stem + ".mzp", exclude=ARCHIVE_NAME)
		if original is None:
			raise ValueError(f"{path.name}: {path.stem}.mzp not found in the game archives")
		full = decode_mzp(original).convert("RGBA")
		height = full.height // LANGUAGE_BANDS
		if image.size == full.size:  # whole image (not made of language bands)
			return encode_mzp_delta(original, image)
		if image.size != (full.width, height):
			raise ValueError(f"{path.name}: {image.width}x{image.height} instead of {full.width}x{height} "
			                 f"(English band) or {full.width}x{full.height} (whole image)")
		full.paste(image.convert("RGBA"), (0, ENGLISH_BAND * height))
		return encode_mzp_delta(original, full)


def build_archive(lines: list[str], titles_csv: str, images_dir: str, fonts_dir: str, game_dir: str) -> dict[str, bytes]:
	files: dict[str, bytes] = {}

	# English resources, under their French name. The DLL redirects a name written in WoH.exe
	# only if the archive holds its French version: only the names built by the game (prefix +
	# "_en" suffix, always redirected) need a copy.
	exe = (Path(game_dir) / "WoH.exe").read_bytes()
	english = {}
	for archive in ENGLISH_ARCHIVES:
		for name, data in read_hfa(str(Path(game_dir) / archive)).items():
			new = french_name(name)
			if new:
				english[new] = data
				if name.encode("utf-16-le") not in exe:
					files[new] = data

	# Translated images (PNG converted to .mzp or .cbg, encoded in parallel) and fonts
	images = []
	for path in sorted(Path(images_dir).glob("*.png")):
		# English resource (name_fr.png), otherwise image shared by all languages (imgNNNN, nz1…),
		# which keeps its name: version.dll redirects the entry of its archive to ours
		if path.with_suffix(".cbg").name in english:
			images.append((path.with_suffix(".cbg").name, path))
		else:
			images.append((path.stem + ".mzp", path))
	with ProcessPoolExecutor() as pool:
		encoded = pool.map(_encode_image, [path for _, path in images], [name for name, _ in images],
		                   [game_dir] * len(images))
		for (name, _), data in zip(images, encoded):
			files[name] = data
	for path in sorted(Path(fonts_dir).iterdir()):
		if path.name not in english:
			raise ValueError(f"{path.name} matches no English resource of the game")
		files[path.name] = path.read_bytes()

	text = "".join(lines).replace("\r\n", "\n").replace("\n", "\r\n")
	files["script_text_fr.ctd"] = text.encode("utf-8")

	with open(titles_csv, encoding="utf-8", newline="") as f:
		rows = list(csv.reader(f))
	if not rows or any(len(row) != 5 for row in rows):
		raise ValueError(f"{titles_csv} must have 5 columns: key, ja, fr, zc, zt")
	titles = io.StringIO(newline="")
	csv.writer(titles, lineterminator="\r\n").writerows(rows)
	files[TEXT5_ENTRY] = titles.getvalue().encode("utf-8")
	files[DATA_PATCHES_ENTRY] = data_patches(images_dir) + line_breaks.data_patches()

	return files


def build_patch(lines: list[str], titles_csv: str, images_dir: str, fonts_dir: str, readme: str,
		game_dir: str, output_dir: str, patch_name: str) -> Path:
	output = Path(output_dir).resolve()
	package = output / patch_name
	if package.exists():
		shutil.rmtree(package)
	package.mkdir(parents=True)

	write_hfa(str(package / ARCHIVE_NAME), build_archive(lines, titles_csv, images_dir, fonts_dir, game_dir))
	shutil.copy2(DLL_PATH, package / DLL_NAME)
	shutil.copy2(readme, package / Path(readme).name)

	return Path(shutil.make_archive(str(output / patch_name), "zip", package))
