import sys

OKGREEN = '\033[92m'
ENDC = '\033[0m'

def progress(count, total, status=''):
	bar_len = 20
	filled_len = int(round(bar_len * count / float(total)))

	percents = round(100.0 * count / float(total), 1)
	bar = '=' * filled_len + '-' * (bar_len - filled_len)

	sys.stdout.write(f"{OKGREEN}[{bar}] {percents}% {status}{ENDC}\r")


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

# compte le nombre d'espaces à la fin de la ligne
def nb_espaces_fin_ligne(ligne: str):
	return len(ligne) - len(ligne.rstrip()) - 1