import re
import sys

from utils.line_format import transform_ruby

GREEN = '\033[92m'
RED = '\033[91m'
BLUE = '\033[94m'
ENDC = '\033[0m'
CLEAN_END = '\033[K'

def progress(count: float, total: float, label: str, color: str = GREEN):
	if count % (total // 100) == 0 or count == total:
		bar_len = 20
		filled_len = int(bar_len * count / total)

		percents = int(100 * count / total)
		bar = '=' * filled_len + '-' * (bar_len - filled_len)

		sys.stdout.write(f"{color}{label} [{bar}] {percents}%{ENDC}{CLEAN_END}\r")
		sys.stdout.flush()

def get_file_lines(path):
	try:
		with open(path, 'r', encoding="utf-8") as f:
			return f.readlines()
	except Exception as e:
		print(f"Erreur lors de la lecture du fichier {path}: {e}")
		return None


def write_file_lines(path: str, lignes: list):
	try:
		with open(path, 'w', encoding="utf-8") as f:
			f.writelines(lignes)
	except Exception as e:
		print(f"Erreur lors de l'écriture du fichier {path}: {e}")

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