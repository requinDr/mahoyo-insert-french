import csv

csv_columns = ["Ligne", "Texte", "Traduction"]
CSV_DELIMITER = ','

def creer_csv(chemin: str, lignes: dict):
    try:
        with open(chemin, 'w', encoding="utf-8", newline='') as f:
            writer = csv.writer(f, delimiter=CSV_DELIMITER, quotechar='"', quoting=csv.QUOTE_MINIMAL)
            writer.writerow(csv_columns)
            for key, value in lignes.items():
                writer.writerow([key, value.strip(), ""])
    except Exception as e:
        print(f"Erreur lors de l'écriture du fichier de sortie: {e}")


# renvoit sous la forme d'un dictionnaire avec comme clé
# la première colonne et comme valeur la 3e colonne
def lire_csv(chemin):
    try:
        with open(chemin, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=CSV_DELIMITER)
            return {int(row[csv_columns[0]]): row for row in reader}
    except Exception as e:
        print(f"Erreur lors de la lecture du fichier {chemin}: {e}")
        return None