"""Construit le patch Steam : version.dll + data00999.hfa, à copier dans le dossier du jeu."""
import csv
import io
import re
import shutil
from pathlib import Path

from PIL import Image

from utils.steam.cbg import encode_cbg
from utils.steam.hfa import find_in_archives, read_hfa, write_hfa
from utils.steam.menu_cursors import DATA_PATCHES_ENTRY, data_patches
from utils.steam.mzp import encode_mzp

ARCHIVE_NAME = "data00999.hfa"
DLL_NAME = "version.dll"
TEXT5_ENTRY = "TEXT5_fr.csv"  # nom attendu par native/version.c
# Archives Steam contenant les images, polices et textes propres à l'anglais
ENGLISH_ARCHIVES = ("data00000.hfa", "data00100.hfa")
# Précompilée depuis native/version.c (voir native/build_dll.py)
DLL_PATH = Path(__file__).resolve().parents[2] / "native" / "version.dll"


# Ressources communes à toutes les langues : même table que shared_names dans native/version.c
SHARED_NAMES = {"mode1.cbg": "modfr.cbg"}
# Images .mzp communes à toutes les langues (une bande par langue) : le script les désigne
# par leur nom, la version traduite garde donc le même nom (version.dll redirige alors
# l'entrée d'origine de son archive vers notre fichier).
SHARED_IMAGE = re.compile(r"img\d{4}")


def french_name(name: str) -> str | None:
	"""Même règle que french_name() dans native/version.c."""
	if name in SHARED_NAMES:
		return SHARED_NAMES[name]
	new = re.sub(r"_en(?=[_.])", "_fr", name)
	if new.startswith("Font010"):
		new = "Font040" + new[7:]
	return new if new != name else None


def build_archive(lines: list[str], titles_csv: str, images_dir: str, fonts_dir: str, game_dir: str) -> dict[str, bytes]:
	files: dict[str, bytes] = {}

	# Chaque ressource anglaise a une copie française, pour que toutes les
	# redirections faites par la DLL trouvent leur fichier.
	for archive in ENGLISH_ARCHIVES:
		for name, data in read_hfa(str(Path(game_dir) / archive)).items():
			new = french_name(name)
			if new:
				files[new] = data

	# Images traduites (PNG converties en .cbg ou .mzp) et polices
	assets = []
	for path in sorted(Path(images_dir).glob("*.png")):
		shared = SHARED_IMAGE.fullmatch(path.stem)
		if shared:
			original = find_in_archives(game_dir, path.stem + ".mzp", exclude=ARCHIVE_NAME)
			if original is None:
				raise ValueError(f"{path.name} : {path.stem}.mzp introuvable dans les archives du jeu")
			with Image.open(path) as image:
				files[path.stem + ".mzp"] = encode_mzp(original, image)
		else:
			assets.append((path.with_suffix(".cbg").name, path))
	assets += [(path.name, path) for path in sorted(Path(fonts_dir).iterdir())]
	for name, path in assets:
		if name not in files:
			raise ValueError(f"{path.name} ne correspond à aucune ressource anglaise du jeu")
		if path.suffix == ".png":
			with Image.open(path) as image:
				files[name] = encode_cbg(image)
		else:
			files[name] = path.read_bytes()

	text = "".join(lines).replace("\r\n", "\n").replace("\n", "\r\n")
	files["script_text_fr.ctd"] = text.encode("utf-8")

	with open(titles_csv, encoding="utf-8", newline="") as f:
		rows = list(csv.reader(f))
	if not rows or any(len(row) != 5 for row in rows):
		raise ValueError(f"{titles_csv} doit contenir 5 colonnes : clé, ja, fr, zc, zt")
	titles = io.StringIO(newline="")
	csv.writer(titles, lineterminator="\r\n").writerows(rows)
	files[TEXT5_ENTRY] = titles.getvalue().encode("utf-8")
	files[DATA_PATCHES_ENTRY] = data_patches(images_dir)

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
