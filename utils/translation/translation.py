import os
import re

import utils.config_importer as conf
import utils.translation.translate_csv as csv
from utils.steam.filesmap import map as map_fichiers
from utils.line_format import format_line_to_steam, transform_ruby
from utils.utils import get_file_lines, progress, write_file_lines

# compte le nombre d'espaces au début de la ligne jusqu'au premier caractère
def nb_espaces_debut_ligne(ligne: str):
	return len(ligne) - len(ligne.lstrip())


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
			# on cherche l'indice de la ligne précédente dans la ligne split
			indice_ligne_precedente = ligne_fr_split.index(ligne_precedente) if ligne_precedente in ligne_fr_split else None
			# si on trouve l'indice, on prend la ligne suivante
			if indice_ligne_precedente is not None and indice_ligne_precedente + 1 < len(ligne_fr_split):
				return ligne_fr_split[indice_ligne_precedente + 1].strip(), last_found_idx + idx

	return None, None

script_fr_mem: list[str] = get_file_lines(conf.script_source)
sourceScriptIndent: list[str] = get_file_lines(conf.script_source_indent)
csv_missing = dict()
csv_dict = csv.get_csv(conf.csv_input) if not conf.creer_csv else None


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

	isInCsv = not conf.creer_csv and (idx + 1) in csv_dict
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
		elif not conf.creer_csv:
			csv_missing[idx + 1] = current_line
	
	if isInCsv and nbStartSpaces != "":
		remplace_dans_script(idx, script_fr_mem[idx], int(nbStartSpaces))

	return last_found_idx


def post_process(script_fr: list[str]):
	for i, ligne in enumerate(script_fr):
		ligne = ligne.replace('ー', '―')
		ligne = ligne.replace('／', '/')
		script_fr[i] = ligne

	return script_fr


def generate_updated_translation():
	global script_fr_mem
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

			last_found_idx = line_process(idx, ligne, og_lines, tr_lines, last_found_idx)
			
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