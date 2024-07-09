import csv

columns = ["Ligne", "Traduction", "Espaces placés au début", "Révision 2022 (pour référence)"]
CSV_DELIMITER = ','

def create(chemin: str, lignes: dict):
	try:
		with open(chemin, 'w', encoding="utf-8", newline='') as f:
			writer = csv.writer(f, delimiter=CSV_DELIMITER, quotechar='"', quoting=csv.QUOTE_MINIMAL)
			writer.writerow(columns)
			for key, value in lignes.items():
				writer.writerow([key, "", "", value.strip()])
		
		print(f"Traductions manquantes inscrites dans {chemin}")
	except Exception as e:
		print(f"Erreur lors de l'écriture du fichier de sortie: {e}")

def read_csv_from_name(chemin):
	try:
		with open(chemin, encoding="utf-8") as f:
			reader = csv.reader(f, delimiter=',')
			return [row for row in reader]
	except Exception as e:
		print(f"Erreur lors de la lecture du fichier {chemin}: {e}")
		return None

# renvoit sous la forme d'un dictionnaire avec comme clé
# la première colonne et comme valeur la 3e colonne
def read_csv_dict_from_name(chemin):
	try:
		with open(chemin, encoding="utf-8") as f:
			reader = csv.DictReader(f, delimiter=CSV_DELIMITER)
			return {int(row[columns[0]]): row for row in reader}
	except Exception as e:
		print(f"Erreur lors de la lecture du fichier {chemin}: {e}")
		return None

def get_csv(pathOrUrl):
	return read_csv_dict_from_name(pathOrUrl)