import os
import time
import re
import configparser

from utils.utils import BLUE, RED, find_og_line_idx, get_file_lines, get_partial_translation, recupere_ligne_traduite, write_file_lines, progress, nb_espaces_debut_ligne
from utils.line_format import transform_ruby, format_line_to_steam
from utils.translate_csv import create_csv, get_csv, csv_columns
from utils.steam.filesmap import map as map_fichiers
from utils.steam.translate_swap import swap_char as swap_chars
from utils.switch.utils import extract_switch_line_offset

config = configparser.ConfigParser()
config.read('config.ini')

script_source = config['paths']['script_source']
script_source_indent = config['paths']['script_source_indent']
dossier_sources_jp = config['paths']['dossier_sources_jp']
dossier_sources_fr = config['paths']['dossier_sources_fr']
csv_name_or_url = config['csv']['csv_name_or_url']
creer_csv = config.getboolean('csv', 'create_csv')
script_sortie = config['steam']['script_steam']
remplacer_caracteres = config.getboolean('steam', 'swap_characters')
dossier_switch = config['switch']['dossier_switch']

script_fr_mem: list[str] = get_file_lines(script_source)
sourceScriptIndent: list[str] = get_file_lines(script_source_indent)
csv_missing = dict()
csv_dict = get_csv(csv_name_or_url) if not creer_csv else None


def remplace_dans_script(indice: int, ligne: str, nbStartSpaces: int = -1):
	global script_fr_mem

	if nbStartSpaces == -1:
		nbStartSpaces = nb_espaces_debut_ligne(sourceScriptIndent[indice])

	script_fr_mem[indice] = format_line_to_steam(ligne, nbStartSpaces)


def line_process(idx: int, current_line: str, og_lines: list[str], tr_lines: list[str], last_found_idx: int) -> int:
	global csv_missing

	isInCsv = not creer_csv and (idx + 1) in csv_dict
	if isInCsv:
		csv_row = csv_dict[idx + 1]
		translation = csv_row[csv_columns[1]]
		nbStartSpaces = int(csv_row[csv_columns[2]]) if csv_row[csv_columns[2]] != "" else -1

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
		ligne_partielle = get_partial_translation(idx, og_lines, tr_lines, script_fr_mem, last_found_idx)
		if ligne_partielle is not None:
			remplace_dans_script(idx, ligne_partielle)
		else:
			csv_missing[idx + 1] = current_line
	
	if isInCsv and nbStartSpaces != "":
			remplace_dans_script(idx, script_fr_mem[idx], int(nbStartSpaces))

	return last_found_idx


def create_steam_file():
	total_lignes = len(script_fr_mem)
	last_found_idx: int = 0
	
	for idx, ligne in enumerate(script_fr_mem):
		progress(idx, total_lignes - 1, "Steam\t", BLUE)
		
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
	
	print("\r")
	lines_to_write = swap_chars(script_fr_mem.copy()) if remplacer_caracteres else script_fr_mem
	write_file_lines(script_sortie, lines_to_write)

	if creer_csv:
		create_csv(csv_name_or_url, csv_missing)
		print(f"Lignes non trouvées : {len(csv_missing)} ({len(csv_missing) / total_lignes * 100:.2f}%)")


def update_switch_files():
	files = os.listdir(dossier_switch)
	total_files = len(files)

	for idx, file in enumerate(files):
		progress(idx, total_files - 1, "Switch\t", RED)

		file_path = os.path.join(dossier_switch, file)
		lines = get_file_lines(file_path)

		for i in range(len(lines)):
			if lines[i].startswith("[sha:"):
				offset = extract_switch_line_offset(lines[i + 1])
				if offset is not None:
					# on remplace la ligne par la ligne française
					lines[i + 3] = script_fr_mem[offset]

		write_file_lines(file_path, lines)

	print("\n")


if __name__ == "__main__":
	debut = time.time()

	create_steam_file()
	update_switch_files()
	
	fin = time.time()
	temps_execution = fin - debut
	print(f"Terminé en {temps_execution:.2f} secondes !")