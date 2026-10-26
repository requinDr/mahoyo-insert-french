"""Texts of the Discord Rich Presence: one line per resource of the game that starts a scene
or a menu (scene script name.chs, menu background), "name<TAB>details<TAB>state", shown by
version.dll when the game reads that resource."""
import csv
import json
import re
from pathlib import Path

from utils.steam.hfa import archive_names

ENTRY = "discord_fr.txt"  # name expected by native/version.c
IMAGE_TEXTS = Path(__file__).resolve().parents[2] / "sources" / "image-texts.json"

# Prefix of the scene scripts, chapter number, chapter title image (none for the interludes)
CHAPTERS = [
	("1", "1", "0409"), ("1dot5", "1.5", None), ("2", "2", "0410"), ("3", "3", "0411"), ("4", "4", "0412"),
	("5a", "5", "0414"), ("5b", "5", "0413"), ("6", "6", "0415"), ("7", "7", "0416"), ("8", "8", "0417"),
	("8dot5", "8.5", None), ("9", "9", "0418"), ("a", "10", "0419"), ("b", "11", "0420"), ("c", "12", "0421"),
	("d", "13", "0422"),
]
TEATIME_NUMBERS = {"a": "10", "b": "11", "c": "12"}
EXTRA_STORY = "Histoire supplémentaire"
# Backgrounds read each time the menu is shown: no texts, only the game is shown
MENUS = {"title_bg2.cbg": ("", ""), "archive_background.cbg": ("", "")}


def presence(scene: str, titles: dict[str, str], system: dict[str, str]) -> tuple[str, str] | None:
	"""Details and state shown for a scene script (name without .chs), None for the others
	(menus, opening, tests)."""
	for prefix, number, title in CHAPTERS:
		if re.fullmatch(rf"{prefix}(_.*)?", scene):
			return f"Chapitre {number}", titles[title] if title else ""
	if match := re.fullmatch(r"teatime(\w+)", scene):
		number = TEATIME_NUMBERS.get(match[1], match[1])
		return system.get(f"SYSMES_TEATIME_{number.upper()}", f"L'heure du thé {number}"), ""
	if match := re.fullmatch(r"nz(\d)", scene):
		return system[f"SYSMES_ARCHIVE_{51 + int(match[1]):03d}"], ""
	if scene.startswith("wik_"):
		return system["SYSMES_ARCHIVE_071"], EXTRA_STORY
	if re.fullmatch(r"sp\d", scene):
		return EXTRA_STORY, ""
	if scene == "staffroll":
		return "Générique de fin", ""
	return None


def presence_table(game_dir: str, titles_csv: str, exclude: str) -> bytes:
	with open(IMAGE_TEXTS, encoding="utf-8") as f:
		titles = json.load(f)["chapter_titles"]
	with open(titles_csv, encoding="utf-8", newline="") as f:
		system = {row[0]: row[2] for row in csv.reader(f)}
	lines = []
	for name in sorted(archive_names(game_dir, exclude=exclude)):
		texts = MENUS[name] if name in MENUS else presence(name[:-len(".chs")], titles, system) if name.endswith(".chs") else None
		if texts:
			lines.append("\t".join((name, *texts)))
	return ("\n".join(lines) + "\n").encode("utf-8")
