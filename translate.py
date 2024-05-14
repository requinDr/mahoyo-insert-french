import os
import shutil
import time
import configparser

from utils.utils import CLEAN_END, find_og_line_idx, get_file_lines, get_partial_translation, recupere_ligne_traduite, write_file_lines, progress, nb_espaces_debut_ligne
from utils.line_format import format_line_to_steam
import utils.translate_csv as csv
from utils.steam.filesmap import map as map_fichiers
from utils.steam.translate_swap import swap_char_in_script
from utils.switch.utils import extract_switch_line_offset
import utils.converters.HunexFileArchiveTool.hunex_file_archive_tool as hfa

config = configparser.ConfigParser()
config.read('config.ini')

script_source = config['paths']['script_source']
script_source_indent = config['paths']['script_source_indent']
dossier_sources_jp = config['paths']['dossier_sources_jp']
dossier_sources_fr = config['paths']['dossier_sources_fr']
generated_translation = config['paths']['generated_translation']
csv_input = config['csv']['csv_input']
csv_output = config['csv']['csv_output']
creer_csv = config.getboolean('csv', 'create_csv')
output_steam_patch_folder = config['steam']['output_steam_patch_folder']
input_steam_patch_folder = config['steam']['input_steam_patch_folder']
steam_hfa_name = config['steam']['steam_hfa_name']
remplacer_caracteres = config.getboolean('steam', 'swap_characters')
output_switch_folder = config['switch']['output_switch_folder']

script_fr_mem: list[str] = get_file_lines(script_source)
sourceScriptIndent: list[str] = get_file_lines(script_source_indent)
csv_missing = dict()
csv_dict = csv.get_csv(csv_input) if not creer_csv else None


# nbStartSpaces = -1 pour ne pas modifier le nombre d'espaces
# nbStartSpaces = -2 pour centrer le texte
def remplace_dans_script(indice: int, ligne: str, nbStartSpaces: int = -1):
	global script_fr_mem

	if nbStartSpaces == -1:
		nbStartSpaces = nb_espaces_debut_ligne(sourceScriptIndent[indice])

	script_fr_mem[indice] = format_line_to_steam(ligne, nbStartSpaces)


# Traite une ligne du script
# Retourne l'indice de la dernière ligne trouvée
def line_process(idx: int, current_line: str, og_lines: list[str], tr_lines: list[str], last_found_idx: int) -> int:
	global csv_missing

	isInCsv = not creer_csv and (idx + 1) in csv_dict
	if isInCsv:
		csv_row = csv_dict[idx + 1]
		translation = csv_row[csv.columns[1]]
		nbStartSpaces = csv_row[csv.columns[2]]
		match nbStartSpaces:
			case "": # aucune indentation précisée
				nbStartSpaces = -1
			case "center": # centrage du texte
				nbStartSpaces = -2
			case _: # indentation précisée
				nbStartSpaces = int(nbStartSpaces)

	# Si l'indice de la ligne est dans la première colonne du csv
	# et qu'une traduction est renseignée, on remplace la ligne par la traduction
	if isInCsv and translation.strip() != "":
		remplace_dans_script(idx, translation, nbStartSpaces)
		return last_found_idx
	
	# S'il n'y a que des espaces dans la ligne, on passe à la suivante
	if current_line.strip() == "":
		return last_found_idx

	indice = find_og_line_idx(og_lines, current_line)
	if indice is not None:
		last_found_idx = indice
		ligne_traduite = recupere_ligne_traduite(indice, tr_lines)
		if ligne_traduite:
			remplace_dans_script(idx, ligne_traduite)
	else:
		# si la ligne n'est pas trouvée, on cherche si elle est incluse dans une autre ligne
		ligne_partielle, indice = get_partial_translation(idx, og_lines, tr_lines, script_fr_mem, last_found_idx)
		if ligne_partielle is not None:
			last_found_idx = indice
			remplace_dans_script(idx, ligne_partielle)
		elif not creer_csv:
			csv_missing[idx + 1] = current_line
	
	if isInCsv and nbStartSpaces != "":
		remplace_dans_script(idx, script_fr_mem[idx], int(nbStartSpaces))

	return last_found_idx


def generate_updated_translation():
	total_lignes = len(script_fr_mem)
	last_found_idx: int = 0
	
	for idx, ligne in enumerate(script_fr_mem):
		progress(idx, total_lignes - 1, "Récupèration des traductions\t")
		
		try:
			# Si l'indice de la ligne est dans la map, on change le fichier actif
			if (idx + 1) in map_fichiers:
				current_file = map_fichiers[idx + 1]
				og_file_path = os.path.join(dossier_sources_jp, current_file)
				og_lines = get_file_lines(og_file_path)
				tr_file_path = os.path.join(dossier_sources_fr, current_file)
				tr_lines = get_file_lines(tr_file_path)

			last_found_idx = line_process(idx, ligne, og_lines, tr_lines, last_found_idx)
			
		except Exception as e:
			print(f"Erreur lors du traitement de la ligne {idx + 1}: {e}. Passage à la ligne suivante.")
	
	# print("\r")

	write_file_lines(generated_translation, script_fr_mem)

	if creer_csv:
		csv.create(csv_output, csv_missing)
		print(f"Lignes non trouvées : {len(csv_missing)} ({len(csv_missing) / total_lignes * 100:.2f}%)")
		print(f"Fichier CSV créé")
	
	return script_fr_mem


def create_steam_file(new_lines: list[str]):
	progress(0, 100, "Steam\t")
	lines_to_write = swap_char_in_script(new_lines.copy()) if remplacer_caracteres else new_lines
	progress(20, 100, "Steam\t")
	hfa.extract(f"{input_steam_patch_folder}/{steam_hfa_name}.hfa")
	progress(40, 100, "Steam\t")
	write_file_lines(f"{steam_hfa_name}/0000_script_text_en.ctd", lines_to_write)
	progress(60, 100, "Steam\t")
	hfa.build(steam_hfa_name, f"{steam_hfa_name}.hfa", output_steam_patch_folder)
	progress(80, 100, "Steam\t")
	if os.path.exists(steam_hfa_name):
		shutil.rmtree(steam_hfa_name, ignore_errors=True)
	progress(100, 100, "Steam\t")
	print(f"Patch Steam créé : {steam_hfa_name}.hfa{CLEAN_END}", end="\n")

def update_switch_files(new_lines: list[str]):
	files = os.listdir(output_switch_folder)
	total_files = len(files)

	for idx, file in enumerate(files):
		progress(idx, total_files - 1, "Switch\t")

		file_path = os.path.join(output_switch_folder, file)
		lines = get_file_lines(file_path)

		for i in range(len(lines)):
			if lines[i].startswith("[sha:"):
				offset = extract_switch_line_offset(lines[i + 1])
				if offset is not None:
					# on remplace la ligne par la traduction
					lines[i + 3] = new_lines[offset]

		write_file_lines(file_path, lines)

	print(f"Fichiers Switch pour deepLuna mis à jour dans {output_switch_folder}", end="\n")


if __name__ == "__main__":
	debut = time.time()

	new_lines = generate_updated_translation()
	create_steam_file(new_lines)
	update_switch_files(new_lines)
	
	fin = time.time()
	temps_execution = fin - debut
	print(f"\nTerminé en {temps_execution:.2f} secondes !")