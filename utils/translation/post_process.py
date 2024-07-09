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

def replacements(line: str):
	line = line.replace('ー', '―')
	line = line.replace('–', '―')
	line = line.replace('／', '/')
	return line

def post_process(script_fr: list[str]):
	for i, ligne in enumerate(script_fr):
		isInCsv, translation, nbStartSpaces = override_translation(i)
		if isInCsv:
			if translation is not None:
				ligne =  format_line_to_steam(translation)
			if nbStartSpaces is not None and nbStartSpaces != -1:
				ligne = set_indentation(ligne, nbStartSpaces)

		ligne = replacements(ligne)

		script_fr[i] = ligne

	return script_fr
