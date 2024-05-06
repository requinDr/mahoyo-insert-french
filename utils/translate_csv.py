import base64
import csv
import io
import requests

from utils.github_api import get_content_from_github, is_github_url

csv_columns = ["Ligne", "Texte", "Traduction", "Espaces placés au début"]
CSV_DELIMITER = ','

def create_csv(chemin: str, lignes: dict):
    try:
        with open(chemin, 'w', encoding="utf-8", newline='') as f:
            writer = csv.writer(f, delimiter=CSV_DELIMITER, quotechar='"', quoting=csv.QUOTE_MINIMAL)
            writer.writerow(csv_columns)
            for key, value in lignes.items():
                writer.writerow([key, value.strip(), ""])
        
        print(f"Traductions manquantes inscrites dans {chemin}")
    except Exception as e:
        print(f"Erreur lors de l'écriture du fichier de sortie: {e}")


# renvoit sous la forme d'un dictionnaire avec comme clé
# la première colonne et comme valeur la 3e colonne
def read_csv_from_name(chemin):
    try:
        with open(chemin, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=CSV_DELIMITER)
            return {int(row[csv_columns[0]]): row for row in reader}
    except Exception as e:
        print(f"Erreur lors de la lecture du fichier {chemin}: {e}")
        return None
    
def read_csv_from_github(url):
    try:
        content = get_content_from_github(url)

        # Lire le contenu du fichier CSV
        reader = csv.DictReader(io.StringIO(content), delimiter=',')
        return {int(row[next(iter(row))]): row for row in reader}
    except Exception as e:
        print(f"Erreur lors de la lecture de l'URL {url} via l'API GitHub : {e}")
        return None

def get_csv(pathOrUrl):
    if is_github_url(pathOrUrl):
        return read_csv_from_github(pathOrUrl)
    else:
        return read_csv_from_name(pathOrUrl)