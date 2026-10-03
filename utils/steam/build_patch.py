"""Construit le patch Steam : version.dll + data00999.hfa, à copier dans le dossier du jeu."""
import csv
import io
import re
import shutil
from concurrent.futures import ProcessPoolExecutor
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


def french_name(name: str) -> str | None:
	"""Même règle que french_name() dans native/version.c."""
	if name in SHARED_NAMES:
		return SHARED_NAMES[name]
	new = re.sub(r"_en(?=[_.])", "_fr", name)
	if new.startswith("Font010"):
		new = "Font040" + new[7:]
	return new if new != name else None


def _encode_image(path: Path, name: str, game_dir: str) -> bytes:
	"""PNG converti au format du jeu : .cbg pour une ressource propre à l'anglais, .mzp pour
	une image commune à toutes les langues (à partir de l'originale)."""
	with Image.open(path) as image:
		if name.endswith(".cbg"):
			return encode_cbg(image)
		original = find_in_archives(game_dir, path.stem + ".mzp", exclude=ARCHIVE_NAME)
		if original is None:
			raise ValueError(f"{path.name} : {path.stem}.mzp introuvable dans les archives du jeu")
		return encode_mzp(original, image)


def build_archive(lines: list[str], titles_csv: str, images_dir: str, fonts_dir: str, game_dir: str) -> dict[str, bytes]:
	files: dict[str, bytes] = {}

	# Ressources propres à l'anglais, sous leur nom français. La DLL ne redirige un nom écrit
	# en clair dans WoH.exe que si l'archive contient sa version française : seuls les noms
	# composés par le jeu (préfixe + suffixe "_en", toujours redirigé) ont besoin d'une copie.
	exe = (Path(game_dir) / "WoH.exe").read_bytes()
	english = {}
	for archive in ENGLISH_ARCHIVES:
		for name, data in read_hfa(str(Path(game_dir) / archive)).items():
			new = french_name(name)
			if new:
				english[new] = data
				if name.encode("utf-16-le") not in exe:
					files[new] = data

	# Images traduites (PNG converties en .mzp ou .cbg), encodées en parallèle, et polices
	images = []
	for path in sorted(Path(images_dir).glob("*.png")):
		# ressource anglaise (nom_fr.png), sinon image commune à toutes les langues (imgNNNN, nz1…),
		# qui garde son nom : version.dll redirige l'entrée de son archive vers la nôtre
		if path.with_suffix(".cbg").name in english:
			images.append((path.with_suffix(".cbg").name, path))
		else:
			images.append((path.stem + ".mzp", path))
	# les .mzp d'abord, comme les images communes s'ajoutent aux ressources anglaises copiées
	images.sort(key=lambda image: not image[0].endswith(".mzp"))
	with ProcessPoolExecutor() as pool:
		encoded = pool.map(_encode_image, [path for _, path in images], [name for name, _ in images],
		                   [game_dir] * len(images))
		for (name, _), data in zip(images, encoded):
			files[name] = data
	for path in sorted(Path(fonts_dir).iterdir()):
		if path.name not in english:
			raise ValueError(f"{path.name} ne correspond à aucune ressource anglaise du jeu")
		files[path.name] = path.read_bytes()

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
