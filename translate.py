import os
import time
import re
import configparser

from utils.switch.utils import ks_name_to_switch_name
from utils.utils import get_file_lines, write_file_lines, progress, nb_espaces_debut_ligne
from utils.steam.filesmap import map as map_fichiers
from utils.steam.line_format import transform_ruby, format_line_to_steam
from utils.translate_csv import create_csv, get_csv, csv_columns
from utils.translate_swap import swap_char as swap_chars

config = configparser.ConfigParser()
config.read('config.ini')

script_source = config['paths']['script_source']
script_source_indent = config['paths']['script_source_indent']
script_sortie = config['paths']['script_steam']
dossier_switch = config['paths']['dossier_switch']
dossier_sources_jp = config['paths']['dossier_sources_jp']
dossier_sources_fr = config['paths']['dossier_sources_fr']
csv_name_or_url = config['csv']['csv_name_or_url']
creer_csv = config.getboolean('csv', 'create_csv')
remplacer_caracteres = config.getboolean('character_swap', 'remplacer_caracteres')

script_fr_mem: list[str] = get_file_lines(script_source)
sourceScriptIndent = get_file_lines(script_source_indent)
csv_missing = dict()
csv_dict = get_csv(csv_name_or_url) if not creer_csv else None
current_line_idx = 0 # index de la ligne du fichier de la map en cours de traitement


def remplace_dans_script(indice: int, ligne: str, nbStartSpaces: int = -1):
	global script_fr_mem

	if nbStartSpaces == -1:
		nbStartSpaces = nb_espaces_debut_ligne(sourceScriptIndent[indice])

	script_fr_mem[indice] = format_line_to_steam(ligne, nbStartSpaces)

# Cherche la ligne japonaise qu'il faut traduire dans un fichier
# Retourne l'indice de la ligne dans le fichier
def find_og_line_idx(lignes_og: list[str], ligne: str):
	for idx, ligne_og in enumerate(lignes_og):
		if ligne.strip() == ligne_og.strip():
			return idx

	return None

def recupere_ligne_traduite(indice: int, lignes_fr: list[str]):
	if indice < len(lignes_fr):
		return lignes_fr[indice]
	
	return None

# Même fonction qu'au dessus, mais pour les lignes partielles
# Retourne la traduction du morceau de ligne
def get_partial_translation(i: int, og_lines: list[str], tr_lines: list[str]):
	ligne_fr_entiere = None
	ligne = script_fr_mem[i].strip()
	isFirstLine = False

	for idx, ligne_og in enumerate(og_lines[current_line_idx + 1:]):
		if ligne in ligne_og.strip():
			ligne_fr_entiere = tr_lines[current_line_idx + 1 + idx]
			isFirstLine = ligne_og.strip().startswith(ligne)
			break

	if ligne_fr_entiere is not None:
		ligne_fr_entiere = transform_ruby(ligne_fr_entiere)

		# on split la ligne à chaque tags
		ligne_fr_split = re.split(r'\[.*?\]', ligne_fr_entiere)
		# strip all
		ligne_fr_split = [line.strip() for line in ligne_fr_split if line.strip()]

		if len(ligne_fr_split) > 1:
			if isFirstLine:
				return ligne_fr_split[0]

			ligne_precedente = script_fr_mem[i - 1].strip()
			# on cherche l'indice de la ligne précédente dans la ligne split
			indice_ligne_precedente = ligne_fr_split.index(ligne_precedente) if ligne_precedente in ligne_fr_split else None
			# si on trouve l'indice, on prend la ligne suivante
			if indice_ligne_precedente is not None and indice_ligne_precedente + 1 < len(ligne_fr_split):
				return ligne_fr_split[indice_ligne_precedente + 1].strip()

	return None


def line_process(idx: int, current_line: str, og_lines: list[str], tr_lines: list[str]):
	global current_line_idx
	global csv_missing

	# Si l'indice de la ligne est dans la première colonne du csv
	# et qu'une traduction est renseignée, on remplace la ligne par la traduction
	if not creer_csv and (idx + 1) in csv_dict:
		csv_row = csv_dict[idx + 1]
		translation = csv_row[csv_columns[1]]
		nbStartSpaces = int(csv_row[csv_columns[2]]) if csv_row[csv_columns[2]] != "" else -1

		if translation.strip() != "":
			remplace_dans_script(idx, translation, nbStartSpaces)
			return
	
	# S'il n'y a que des espaces dans la ligne, on passe à la suivante
	if current_line.strip() == "":
		return

	indice = find_og_line_idx(og_lines, current_line)
	if indice is not None:
		current_line_idx = indice
		ligne_traduite = recupere_ligne_traduite(indice, tr_lines)
		if ligne_traduite:
			remplace_dans_script(idx, ligne_traduite)
	else:
		# si la ligne n'est pas trouvée, on cherche si elle est incluse dans une autre ligne
		ligne_partielle = get_partial_translation(idx, og_lines, tr_lines)
		if ligne_partielle is not None:
			remplace_dans_script(idx, ligne_partielle)
		else:
			csv_missing[idx + 1] = current_line
	
	if not creer_csv and (idx + 1) in csv_dict:
		csv_row = csv_dict[idx + 1]
		nbStartSpaces = csv_row[csv_columns[2]]
		if nbStartSpaces != "":
			remplace_dans_script(idx, script_fr_mem[idx], int(nbStartSpaces))


def creer_fichier_steam(script_sortie: str):
	global script_fr_mem
	total_lignes = len(script_fr_mem)
	
	for idx, ligne in enumerate(script_fr_mem):
		# si la progression en pourcentage est un nombre entier
		if idx % (total_lignes // 100) == 0:
			progress(idx, total_lignes)
		
		try:
			# Si l'indice de la ligne est dans la map, on change le fichier actif
			if (idx + 1) in map_fichiers:
				current_file = map_fichiers[idx + 1]
				og_file_path = os.path.join(dossier_sources_jp, current_file)
				og_lines = get_file_lines(og_file_path)
				tr_file_path = os.path.join(dossier_sources_fr, current_file)
				tr_lines = get_file_lines(tr_file_path)

			line_process(idx, ligne, og_lines, tr_lines)
			
		except Exception as e:
			print(f"Erreur lors du traitement de la ligne {idx + 1}: {e}. Passage à la ligne suivante.")

	# if remplacer_caracteres:
	# 	script_fr_mem = swap_chars(script_fr_mem)
	
	write_file_lines(script_sortie, swap_chars(script_fr_mem.copy()) if remplacer_caracteres else script_fr_mem)

	if creer_csv:
		create_csv(csv_name_or_url, csv_missing)
		print(f"Lignes non trouvées : {len(csv_missing)} ({len(csv_missing) / total_lignes * 100:.2f}%)")

def update_switch_files():
	for file in os.listdir(dossier_switch):
		file_path = os.path.join(dossier_switch, file)
		lines = get_file_lines(file_path)
		# remove empty lines
		lines = [line for line in lines if line.strip()]
		print(f"Updating {file_path}... {round(len(lines) / 5)} lines.")
		for i, line in enumerate(lines):
			if line.startswith("[sha:"):
				# on récupère le offset
				offset = int(re.match(r".*Offset (\d+)\..*", lines[i + 1]).group(1))
				if offset is not None:
					# on remplace la ligne par la ligne française
					lines[i + 3] = script_fr_mem[offset]

		write_file_lines(file_path, lines)


if __name__ == "__main__":
	debut = time.time()

	creer_fichier_steam(script_sortie)
	update_switch_files()
	
	fin = time.time()
	temps_execution = fin - debut
	print(f"Terminé en {temps_execution:.2f} secondes !")