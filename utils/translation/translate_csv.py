import csv

LINE, TRANSLATION, START_SPACES, _ = columns = ["Ligne", "Traduction", "Espaces placés au début", "Révision 2022 (pour référence)"]


def create(path: str, lines: dict[int, str]):
	"""CSV of the script lines without a translation, to fill in."""
	with open(path, 'w', encoding="utf-8", newline='') as f:
		writer = csv.writer(f)
		writer.writerow(columns)
		for number, line in lines.items():
			writer.writerow([number, "", "", line.strip()])
	print(f"Missing translations written to {path}")


def get_csv(path: str) -> dict[int, dict[str, str]]:
	"""Rows of the corrections CSV by line number."""
	with open(path, encoding="utf-8") as f:
		return {int(row[LINE]): row for row in csv.DictReader(f)}
