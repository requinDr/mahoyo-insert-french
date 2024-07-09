import utils.config_importer as conf
from utils.line_format import indent
import utils.translation.translate_csv as csv

csv_dict = csv.get_csv(conf.csv_input) if not conf.creer_csv else None

def override_translation(idx: int)-> tuple[bool, str, int]:
	isInCsv: bool = not conf.creer_csv and (idx + 1) in csv_dict # idx + 1 because csv starts at 1
	translation = None
	nbStartSpaces = None

	if isInCsv:
		csv_row = csv_dict[idx + 1]
		translation = csv_row[csv.columns[1]].strip()
		nbStartSpaces = csv_row[csv.columns[2]].strip()
		match nbStartSpaces:
			case "": # aucune indentation précisée
				nbStartSpaces = -1
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
			# if translation is not None:
			# 	ligne = translation
			if nbStartSpaces is not None and nbStartSpaces >= 0:
				ligne = indent(nbStartSpaces, ligne)

		ligne = replacements(ligne)
		script_fr[i] = ligne

	return script_fr
