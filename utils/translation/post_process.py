import csv as csv_module
import re

import utils.config_importer as conf
from utils.line_format import format_line_to_steam, set_indentation
import utils.translation.translate_csv as csv
from utils.utils import get_file_lines, nb_espaces_debut_ligne

csv_dict = csv.get_csv(conf.csv_input) if not conf.creer_csv else None
sourceScriptIndent: list[str] = get_file_lines(conf.script_source_indent)

def override_translation(idx: int)-> tuple[bool, str, int]:
	idxCsv = idx + 1 # idx + 1 because csv starts at 1
	isInCsv: bool = not conf.creer_csv and (idxCsv) in csv_dict
	translation = None
	nbStartSpaces = None

	if isInCsv:
		csv_row = csv_dict[idxCsv]
		translation = csv_row[csv.columns[1]].strip() or None
		nbStartSpaces = csv_row[csv.columns[2]].strip() or None
		match nbStartSpaces:
			case None: # aucune indentation précisée
				nbStartSpaces = nb_espaces_debut_ligne(sourceScriptIndent[idx])
			case "center": # centrage du texte
				nbStartSpaces = -2
			case _: # indentation précisée
				nbStartSpaces = int(nbStartSpaces)

	return isInCsv, translation, nbStartSpaces

def load_final_replacements(path: str) -> list[tuple[str, str]]:
	def unescape(text: str) -> str:
		return re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), text)
	with open(path, encoding='utf-8', newline='') as f:
		return [(unescape(row['avant']), unescape(row['après'])) for row in csv_module.DictReader(f) if row['avant']]

def post_process(script_fr: list[str]):
	final_replacements = load_final_replacements(conf.replacements_csv)
	for i, ligne in enumerate(script_fr):
		isInCsv, translation, nbStartSpaces = override_translation(i)
		if isInCsv:
			if translation is not None:
				ligne =  format_line_to_steam(translation)
			if nbStartSpaces is not None and nbStartSpaces != -1:
				ligne = set_indentation(ligne, nbStartSpaces)

		for before, after in final_replacements:
			ligne = ligne.replace(before, after)

		script_fr[i] = ligne

	return script_fr
