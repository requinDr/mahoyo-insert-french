import os
import re

import utils.config_importer as conf
from utils.translation.post_process import post_process
import utils.translation.translate_csv as csv
from utils.steam.filesmap import map as map_fichiers
from utils.line_format import format_line_to_steam, set_indentation, transform_ruby
from utils.utils import get_file_lines, nb_espaces_debut_ligne, progress, write_file_lines

sourceScriptIndent: list[str] = get_file_lines(conf.script_source_indent)
csv_missing = dict()

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


# Retourne la traduction du morceau de ligne
# et son indice de ligne
def get_partial_translation(i: int, og_lines: list[str], tr_lines: list[str], script_fr_mem: list[str], last_found_idx: int):
	ligne_fr_entiere = None
	ligne = script_fr_mem[i].strip()
	isFirstLine = False

	for idx, ligne_og in enumerate(og_lines[last_found_idx + 1:]):
		if ligne in ligne_og.strip():
			ligne_fr_entiere = tr_lines[last_found_idx + 1 + idx]
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
				return ligne_fr_split[0], last_found_idx + idx

			ligne_precedente = script_fr_mem[i - 1].strip()
			try:
				# on cherche l'indice de la ligne précédente dans la ligne split, et on prend la ligne suivante
				indice_ligne_precedente = ligne_fr_split.index(ligne_precedente)
				return ligne_fr_split[indice_ligne_precedente + 1].strip(), last_found_idx + idx
			except (ValueError, IndexError):
				pass

	return None, None

def format_line(indice: int, ligne: str):
	ligne = format_line_to_steam(ligne)
	nbStartSpaces = nb_espaces_debut_ligne(sourceScriptIndent[indice])
	ligne = set_indentation(ligne, nbStartSpaces)
	return ligne


# Traite une ligne du script
# Retourne l'indice de la dernière ligne trouvée
def line_process(script_fr_mem: list[str], idx: int, current_line: str, og_lines: list[str], tr_lines: list[str], last_found_idx: int) -> int:
	global csv_missing
	
	# S'il n'y a que des espaces dans la ligne, on passe à la suivante
	if current_line.strip() == "":
		return script_fr_mem, last_found_idx

	indice = find_og_line_idx(og_lines, current_line)
	if indice is not None:
		last_found_idx = indice
		ligne_traduite = recupere_ligne_traduite(indice, tr_lines)
		if ligne_traduite:
			script_fr_mem[idx] = format_line(idx, ligne_traduite)
	else:
		# si la ligne n'est pas trouvée, on cherche si elle est incluse dans une autre ligne
		ligne_partielle, indice = get_partial_translation(idx, og_lines, tr_lines, script_fr_mem, last_found_idx)
		if ligne_partielle is not None:
			last_found_idx = indice
			script_fr_mem[idx] = format_line(idx, ligne_partielle)
		elif not conf.creer_csv:
			csv_missing[idx + 1] = current_line

	return script_fr_mem, last_found_idx

def generate_updated_translation():
	script_fr_mem: list[str] = get_file_lines(conf.script_source)
	total_lignes = len(script_fr_mem)
	last_found_idx: int = 0
	
	for idx, ligne in enumerate(script_fr_mem):
		progress(idx, total_lignes - 1, "Récupèration des traductions\t")
		
		try:
			# Si l'indice de la ligne est dans la map, on change le fichier actif
			if (idx + 1) in map_fichiers:
				current_file = map_fichiers[idx + 1]
				og_file_path = os.path.join(conf.dossier_sources_jp, current_file)
				og_lines = get_file_lines(og_file_path)
				tr_file_path = os.path.join(conf.dossier_sources_fr, current_file)
				tr_lines = get_file_lines(tr_file_path)

			script_fr_mem, last_found_idx = line_process(script_fr_mem, idx, ligne, og_lines, tr_lines, last_found_idx)
			
		except Exception as e:
			print(f"Erreur lors du traitement de la ligne {idx + 1}: {e}. Passage à la ligne suivante.")

	if conf.creer_csv:
		csv.create(conf.csv_output, csv_missing)
		print(f"Lignes non trouvées : {len(csv_missing)} ({len(csv_missing) / total_lignes * 100:.2f}%)")
		print(f"Fichier CSV créé")

	script_fr_mem = post_process(script_fr_mem)
	write_file_lines(conf.generated_translation, script_fr_mem)

	return script_fr_mem


if __name__ == "__main__":
	new_lines = generate_updated_translation()
	print(f"Traduction générée dans {conf.generated_translation}")