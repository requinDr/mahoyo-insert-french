import base64
import csv
import io
import requests

csv_columns = ["Ligne", "Texte", "Traduction"]
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
        # Faire la requête GET à l'API GitHub
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for 4xx and 5xx status codes

        # Extraire le contenu encodé en base64
        content_base64 = response.json()["content"]

        # Décoder le contenu en base64
        content = base64.b64decode(content_base64).decode("utf-8")

        # Lire le contenu du fichier CSV
        reader = csv.DictReader(io.StringIO(content), delimiter=',')
        return {int(row[next(iter(row))]): row for row in reader}
    except Exception as e:
        print(f"Erreur lors de la lecture de l'URL {url} via l'API GitHub : {e}")
        return None

def get_csv(pathOrUrl):
    if pathOrUrl.startswith("http"):
        return read_csv_from_github(pathOrUrl)
    else:
        return read_csv_from_name(pathOrUrl)