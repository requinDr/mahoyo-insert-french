import sys

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