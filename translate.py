import os
import time
import re
import configparser

from utils.utils import get_file_lines, write_file_lines, progress, nb_espaces_debut_ligne, nb_espaces_fin_ligne
from utils.steam.filesmap import map as map_fichiers
from utils.steam.line_format import transform_ruby, format_line_to_steam
from utils.translate_csv import create_csv, get_csv, csv_columns
from utils.translate_swap import swap_char as swap_chars

config = configparser.ConfigParser()
config.read('config.ini')

script_source = config['paths']['script_source']
script_source_indent = config['paths']['script_source_indent']
script_sortie = config['paths']['script_sortie']
dossier_sources_jp = config['paths']['dossier_sources_jp']
dossier_sources_fr = config['paths']['dossier_sources_fr']
csv_name_or_url = config['csv']['csv_name_or_url']
creer_csv = config.getboolean('csv', 'create_csv')
remplacer_caracteres = config.getboolean('character_swap', 'remplacer_caracteres')

script_fr_mem = list([str])
csv_missing = dict()
csv_dict = get_csv(csv_name_or_url) if not creer_csv else None
idx_line = 0 # index de la ligne du fichier de la map en cours de traitement
sourceScriptIndent = get_file_lines(script_source_indent)

def init_script_fr_mem():
	global script_fr_mem
	script_fr_mem = get_file_lines(script_source)

def remplace_dans_script(indice: int, ligne: str, nbStartSpaces: int = -1):
	global script_fr_mem

	if nbStartSpaces == -1:
		nbStartSpaces = nb_espaces_debut_ligne(sourceScriptIndent[indice])
	# nbEndSpaces = nb_espaces_fin_ligne(sourceScriptIndent[indice])

	ligne = format_line_to_steam(ligne, nbStartSpaces)
	script_fr_mem[indice] = ligne

# Cherche la ligne japonaise qu'il faut traduire dans un fichier
# Retourne l'indice de la ligne dans le fichier
def trouver_jp_dans_fichier(lignes_og: list[str], ligne: str):
	for idx, ligne_og in enumerate(lignes_og):
		if ligne.strip() == ligne_og.strip():
			return idx

	return None

# Même fonction qu'au dessus, mais pour les lignes partielles
# Retourne la traduction du morceau de ligne
def trouver_fr_partiel(i: int, original_lines: list[str], new_lines: list[str]):
	ligne_fr_entiere = None
	ligne = script_fr_mem[i].strip()
	isFirstLine = False

	for idx, ligne_og in enumerate(original_lines):
		# La ligne est trouvée dans une autre ligne qui se situe
		# après la dernière ligne trouvée
		if idx <= idx_line:
			continue
		if ligne in ligne_og.strip():
			ligne_fr_entiere = new_lines[idx]
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
				return ligne_fr_split[0].strip()

			ligne_precedente = script_fr_mem[i - 1].strip()
			# on cherche l'indice de la ligne précédente dans la ligne split
			indice_ligne_precedente = ligne_fr_split.index(ligne_precedente) if ligne_precedente in ligne_fr_split else None
			# si on trouve l'indice, on prend la ligne suivante
			if indice_ligne_precedente is not None and indice_ligne_precedente + 1 < len(ligne_fr_split):
				return ligne_fr_split[indice_ligne_precedente + 1].strip()

	return None

def recupere_ligne_traduite(lignes_fr: list[str], indice: int):
	if indice < len(lignes_fr):
		return lignes_fr[indice].strip()
	
	return None

def creer_fichier_steam(script_sortie: str):
	global script_fr_mem
	global idx_line
	global csv_missing

	total_lignes = len(script_fr_mem)
	nb_non_trouvees = 0
	
	for idx, ligne in enumerate(script_fr_mem):
		# si la progression en pourcentage est un nombre entier
		if idx % (total_lignes // 100) == 0:
			progress(idx, total_lignes)
		
		try:
			# Si l'indice de la ligne est dans la map, on change le fichier actif
			if (idx + 1) in map_fichiers:
				fichier_en_cours = map_fichiers[idx + 1]
				chemin_fichier_og = os.path.join(dossier_sources_jp, fichier_en_cours)
				lignes_og = get_file_lines(chemin_fichier_og)
				chemin_fichier_fr = os.path.join(dossier_sources_fr, fichier_en_cours)
				lignes_fr = get_file_lines(chemin_fichier_fr)

			# Si l'indice de la ligne est dans la première colonne du csv,
			# et que la troisième colonne n'est pas vide,
			# on remplace la ligne par la traduction située dans la troisième colonne
			if not creer_csv and (idx + 1) in csv_dict:
				csv_row = csv_dict[idx + 1]
				translation = csv_row[csv_columns[2]]
				nbStartSpaces = int(csv_row[csv_columns[3]]) if csv_row[csv_columns[3]] != "" else -1

				if translation.strip() != "":
					remplace_dans_script(idx, translation, nbStartSpaces)
					continue
			
			# S'il n'y a que des espaces dans la ligne, on passe à la suivante
			if ligne.strip() == "":
				continue

			indice = trouver_jp_dans_fichier(lignes_og, ligne)
			if indice is not None:
				idx_line = indice
				ligne_traduite = recupere_ligne_traduite(lignes_fr, indice)
				if ligne_traduite:
					remplace_dans_script(idx, ligne_traduite)
			else:
				# si la ligne n'est pas trouvée, on cherche si elle est incluse dans une autre ligne
				ligne_partielle = trouver_fr_partiel(idx, lignes_og, lignes_fr)
				if ligne_partielle is not None:
					remplace_dans_script(idx, ligne_partielle)
				else:
					nb_non_trouvees += 1
					csv_missing[idx + 1] = ligne
			
			if not creer_csv and (idx + 1) in csv_dict:
				csv_row = csv_dict[idx + 1]
				nbStartSpaces = csv_row[csv_columns[3]]
				if nbStartSpaces != "":
					remplace_dans_script(idx, script_fr_mem[idx], int(nbStartSpaces))
			
		except Exception as e:
			print(f"Erreur lors du traitement de la ligne {idx + 1}: {e}. Passage à la ligne suivante.")

	if remplacer_caracteres:
		script_fr_mem = swap_chars(script_fr_mem)
	
	write_file_lines(script_sortie, script_fr_mem)

	if creer_csv:
		create_csv(csv_name_or_url, csv_missing)
		print(f"Lignes non trouvées : {nb_non_trouvees} ({nb_non_trouvees / total_lignes * 100:.2f}%)")


if __name__ == "__main__":
	debut = time.time()

	init_script_fr_mem()

	creer_fichier_steam(script_sortie)
	
	fin = time.time()
	temps_execution = fin - debut
	print(f"Terminé en {temps_execution:.2f} secondes !")