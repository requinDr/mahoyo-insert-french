import os
import time
import re
import configparser

from utils.utils import get_file_lines, write_file_lines, progress
from utils.steam.filesmap import map as map_fichiers
from utils.steam.line_format import transform_ruby, format_line_to_steam
from utils.translate_csv import create_csv, read_csv, csv_columns
from utils.translate_swap import swap_char as swap_chars

config = configparser.ConfigParser()
config.read('config.ini')

script_source = config['paths']['script_source']
script_sortie = config['paths']['script_sortie']
dossier_sources_jp = config['paths']['dossier_sources_jp']
dossier_sources_fr = config['paths']['dossier_sources_fr']
nom_csv = config['csv']['nom_csv']
create_csv = config.getboolean('csv', 'create_csv')
remplacer_caracteres = config.getboolean('character_swap', 'remplacer_caracteres')

script_fr_mem = list([str])
csv_missing = dict()
idx_fichier = 0 # index du fichier de la map en cours de traitement


def init_script_fr_mem(lignes: list):
	global script_fr_mem
	script_fr_mem = lignes.copy()

def remplace_dans_script(indice: int, ligne: str, nbStartSpaces: int = 0):
	global script_fr_mem

	ligne = format_line_to_steam(ligne, nbStartSpaces)
	script_fr_mem[indice] = ligne

# Cherche la ligne japonaise qu'il faut traduire dans un fichier
# Retourne l'indice de la ligne dans le fichier
def trouver_jp_dans_fichier(lignes_og: list[str], ligne: str):
	global idx_fichier
	
	for idx, ligne_og in enumerate(lignes_og):
		if ligne.strip() == ligne_og.strip():
			idx_fichier = idx
			return idx

	return None

# Même fonction qu'au dessus, mais pour les lignes partielles
# Retourne la traduction du morceau de ligne
def trouver_fr_partiel(i: int, lignes_og: list[str], lignes_fr: list[str]):
	ligne_fr_entiere = None
	ligne = script_fr_mem[i].strip()
	isFirstLine = False

	for idx, ligne_og in enumerate(lignes_og):
		# La ligne est trouvée dans une autre ligne qui se situe
		# après la dernière ligne trouvée
		if ligne in ligne_og.strip() and idx > idx_fichier:
			ligne_fr_entiere = lignes_fr[idx]
			if ligne_og.strip().startswith(ligne):
				isFirstLine = True
			break

	if ligne_fr_entiere is not None:
		ligne_fr_entiere = transform_ruby(ligne_fr_entiere)

		# on split la ligne à chaque tags
		ligne_fr_split = re.split(r'\[.*?\]', ligne_fr_entiere)
		# strip all
		ligne_fr_split = [ligne.strip() for ligne in ligne_fr_split]
		# remove empty lines
		ligne_fr_split = [ligne for ligne in ligne_fr_split if ligne != ""]

		if len(ligne_fr_split) > 1:
			if isFirstLine:
				return ligne_fr_split[0].strip()
			else:
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

def creer_fichier_steam(lignes_script: list[str], script_sortie: str):
	global script_fr_mem
	global csv_missing

	total_lignes = len(lignes_script)
	csv_dict = read_csv(nom_csv) if not create_csv else None
	nb_non_trouvees = 0
	
	for idx, ligne in enumerate(lignes_script):
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
			if not create_csv and (idx + 1) in csv_dict and csv_dict[idx + 1][csv_columns[2]].strip() != "":
				nbStartSpaces = len(ligne) - len(ligne.lstrip())
				remplace_dans_script(idx, csv_dict[idx + 1][csv_columns[2]]+ "\n", nbStartSpaces)
				continue
			
			# S'il n'y a que des espaces dans la ligne, on passe à la suivante
			if ligne.strip() == "":
				continue

			indice = trouver_jp_dans_fichier(lignes_og, ligne)
			if indice is not None:
				# compte le nombre d'espaces au début de la ligne jusqu'au premier caractère
				nbStartSpaces = len(ligne) - len(ligne.lstrip())
				ligne_traduite = recupere_ligne_traduite(lignes_fr, indice)
				if ligne_traduite:
					remplace_dans_script(idx, ligne_traduite, nbStartSpaces)
			else:
				# si la ligne n'est pas trouvée, on cherche si elle est incluse dans une autre ligne
				ligne_partielle = trouver_fr_partiel(idx, lignes_og, lignes_fr)
				if ligne_partielle is not None:
					nbStartSpaces = len(ligne) - len(ligne.lstrip())
					remplace_dans_script(idx, ligne_partielle, nbStartSpaces)
				else:
					nb_non_trouvees += 1
					csv_missing[idx + 1] = ligne
			
		except Exception as e:
			print(f"Erreur lors du traitement de la ligne {idx + 1}: {e}. Passage à la ligne suivante.")

	if remplacer_caracteres:
		script_fr_mem = swap_chars(script_fr_mem)
	
	write_file_lines(script_sortie, script_fr_mem)

	if create_csv:
		create_csv(nom_csv, csv_missing)
		print(f"Lignes non trouvées : {nb_non_trouvees} ({nb_non_trouvees / total_lignes * 100:.2f}%)")

if __name__ == "__main__":
	debut = time.time()  # début

	lignes_script = get_file_lines(script_source)
	init_script_fr_mem(lignes_script)

	creer_fichier_steam(lignes_script, script_sortie)
	
	fin = time.time()  # fin
	temps_execution = fin - debut
	print(f"Terminé en {temps_execution:.2f} secondes !")