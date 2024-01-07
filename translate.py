import os
import time
import sys
import csv
import re

# map_fichiers is a dict
# key: line number => value: file name
from translate_map import map as map_fichiers

script_fr_mem = list()
csv_missing = dict()

# Le script source ja devrait être modifié pour ne pas avoir de ruby
# avant de lancer le script afin que la traduction puisse être trouvée
script_source = "script_text_ja.txt"
script_sortie = "script_text_fr.txt"

# Les fichiers sources doivent être nettoyés, en UTF-8 et nommés comme dans la map
dossier_sources_jp = "sources-jp"
dossier_sources_fr = "sources-fr"

# Fichier csv avec les lignes non trouvées
# Le numéro de ligne commence à 1. Chaque ligne renseignée avec une traduction
# sera remplacée dans le script de sortie
nom_csv = "lignes_modifiees.csv"
create_csv = True   # /!\ True écrase le fichier existant, False le lit
csv_columns = ["Ligne", "Texte", "Traduction"]

CSV_DELIMITER = ';'
OKGREEN = '\033[92m'
ENDC = '\033[0m'
SPACE = "\u3000"

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
    
def progress(count, total, status=''):
    bar_len = 20
    filled_len = int(round(bar_len * count / float(total)))

    percents = round(100.0 * count / float(total), 1)
    bar = '=' * filled_len + '-' * (bar_len - filled_len)

    sys.stdout.write(f"{OKGREEN}[{bar}] {percents}% {status}{ENDC}\r")

def init_script_fr_mem(lignes: list):
    global script_fr_mem
    script_fr_mem = lignes.copy()

def lire_fichier(chemin):
    try:
        with open(chemin, 'r', encoding="utf-8") as f:
            return f.readlines()
    except Exception as e:
        print(f"Erreur lors de la lecture du fichier {chemin}: {e}")
        return None

def indente(nbStartSpaces: int, ligne: str):
    return SPACE * nbStartSpaces + ligne

def cree_fichier_sortie(chemin: str, lignes: list):
    try:
        with open(chemin, 'w', encoding="utf-8") as f:
            f.writelines(lignes)
    except Exception as e:
        print(f"Erreur lors de l'écriture du fichier de sortie: {e}")

pattern_ruby = r'\[ruby char="([^"]+)" text="([^"]+)"\]'
def modifier_traduction(ligne: str, nbStartSpaces: int = 0):
    # modifie le format du ruby
    match = re.search(pattern_ruby, ligne)
    if match:
        remplacement = f"<{match.group(1)}|{match.group(2)}>"
        ligne = re.sub(pattern_ruby, remplacement, ligne)

    # supprime les tags
    ligne = re.sub(r'\[.*?\]', '', ligne)

    # supprime les espaces en fin de ligne
    ligne = ligne.rstrip() + "\n"

    # indente
    ligne = indente(nbStartSpaces, ligne)

    return ligne

def remplace_dans_script(indice: int, ligne: str, nbStartSpaces: int = 0):
    global script_fr_mem

    ligne = modifier_traduction(ligne, nbStartSpaces)
    script_fr_mem[indice] = ligne

# Cherche la ligne japonaise qu'il faut traduire dans un fichier
# Retourne l'indice de la ligne dans le fichier
def trouver_jp_dans_fichier(lignes_og: list, ligne: str):
    for idx, ligne_og in enumerate(lignes_og):
        if ligne.strip() == ligne_og.strip():
            return idx

    return None

def recupere_ligne_traduite(lignes_fr: list, indice: int, nbStartSpaces: int = 0):
    if indice < len(lignes_fr):
        return lignes_fr[indice].strip()
    
    return None

def creer_fichier_steam(lignes_script: list, script_sortie: str):
    global csv_missing

    total_lignes = len(lignes_script)
    csv_dict = lire_csv(nom_csv) if not create_csv else None
    nb_non_trouvees = 0
    
    for idx, ligne in enumerate(lignes_script):
        # si la progression en pourcentage est un nombre entier
        if idx % (total_lignes // 100) == 0:
            progress(idx, total_lignes)
        
        try:
            # Si l'indice de la ligne est dans la map, on change le fichier actif
            if (idx + 1) in map_fichiers:
                fichier_en_cours = map_fichiers[idx + 1]
                chemin_fichier_og = os.path.join(dossier_sources_jp, fichier_en_cours)
                lignes_og = lire_fichier(chemin_fichier_og)
                chemin_fichier_fr = os.path.join(dossier_sources_fr, fichier_en_cours)
                lignes_fr = lire_fichier(chemin_fichier_fr)

            # Si l'indice de la ligne est dans la première colonne du csv,
            # et que la troisième colonne n'est pas vide,
            # on remplace la ligne par la traduction située dans la troisième colonne
            if not create_csv and (idx + 1) in csv_dict and csv_dict[idx + 1][csv_columns[2]].strip() != "":
                nbStartSpaces = len(ligne) - len(ligne.lstrip())
                remplace_dans_script(idx, csv_dict[idx + 1][csv_columns[2]]+ "\n", nbStartSpaces)
                continue
            
            # S'il n'y a que des espaces dans la ligne, on passe à la suivante
            if ligne.strip() == "":
                continue

            indice = trouver_jp_dans_fichier(lignes_og, ligne)
            if indice is not None:
                # compte le nombre d'espaces au début de la ligne jusqu'au premier caractère
                nbStartSpaces = len(ligne) - len(ligne.lstrip())
                ligne_traduite = recupere_ligne_traduite(lignes_fr, indice)
                if ligne_traduite:
                    remplace_dans_script(idx, ligne_traduite, nbStartSpaces)
            else:
                nb_non_trouvees += 1
                csv_missing[idx + 1] = ligne
            
        except Exception as e:
            print(f"Erreur lors du traitement de la ligne {idx + 1}: {e}. Passage à la ligne suivante.")

    cree_fichier_sortie(script_sortie, script_fr_mem)
    if create_csv:
        creer_csv(nom_csv, csv_missing)
    print(f"Lignes non trouvées : {nb_non_trouvees} ({nb_non_trouvees / total_lignes * 100:.2f}%)")

if __name__ == "__main__":
    debut = time.time()  # début

    lignes_script = lire_fichier(script_source)
    init_script_fr_mem(lignes_script)

    creer_fichier_steam(lignes_script, script_sortie)
    
    fin = time.time()  # fin
    temps_execution = fin - debut
    print(f"Terminé en {temps_execution:.2f} secondes !")