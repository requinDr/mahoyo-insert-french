import sys

OKGREEN = '\033[92m'
ENDC = '\033[0m'

def progress(count, total, status=''):
	bar_len = 20
	filled_len = int(round(bar_len * count / float(total)))

	percents = round(100.0 * count / float(total), 1)
	bar = '=' * filled_len + '-' * (bar_len - filled_len)

	sys.stdout.write(f"{OKGREEN}[{bar}] {percents}% {status}{ENDC}\r")


def get_file_lines(chemin):
	try:
		with open(chemin, 'r', encoding="utf-8") as f:
			return f.readlines()
	except Exception as e:
		print(f"Erreur lors de la lecture du fichier {chemin}: {e}")
		return None


def write_file_lines(chemin: str, lignes: list):
	try:
		with open(chemin, 'w', encoding="utf-8") as f:
			f.writelines(lignes)
	except Exception as e:
		print(f"Erreur lors de l'écriture du fichier de sortie: {e}")