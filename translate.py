import os
import time
import sys
import csv
import re

# map_fichiers is a dict
# key: line number => value: file name
from translate_map import map as map_fichiers

script_fr_mem = list([str])
csv_missing = dict()
idx_fichier = 0 # index du fichier de la map en cours de traitement


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
create_csv = False   # /!\ True écrase le fichier existant, False le lit
csv_columns = ["Ligne", "Texte", "Traduction"]

CSV_DELIMITER = ','
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
def transformer_ruby(ligne: str):
    match = re.search(pattern_ruby, ligne)
    if match:
        remplacement = f"<{match.group(1)}|{match.group(2)}>"
        return re.sub(pattern_ruby, remplacement, ligne)
    return ligne

def modifier_traduction(ligne: str, nbStartSpaces: int = 0):
    # modifie le format du ruby
    ligne = transformer_ruby(ligne)

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
def trouver_jp_dans_fichier(lignes_og: list[str], ligne: str):
    global idx_fichier
    
    for idx, ligne_og in enumerate(lignes_og):
        if ligne.strip() == ligne_og.strip():
            idx_fichier = idx
            return idx

    return None

# Même fonction qu'au dessus, mais pour les lignes partielles
# Retourne la traduction du morceau de ligne
def trouver_fr_partiel(i: int, lignes_og: list[str], lignes_fr: list[str]):
    ligne_fr_entiere = None
    ligne = script_fr_mem[i].strip()
    isFirstLine = False

    for idx, ligne_og in enumerate(lignes_og):
        # La ligne est trouvée dans une autre ligne qui se situe
        # après la dernière ligne trouvée
        if ligne in ligne_og.strip() and idx > idx_fichier:
            ligne_fr_entiere = lignes_fr[idx]
            if ligne_og.strip().startswith(ligne):
                isFirstLine = True
            break

    if ligne_fr_entiere is not None:
        ligne_fr_entiere = transformer_ruby(ligne_fr_entiere)

        # on split la ligne à chaque tags
        ligne_fr_split = re.split(r'\[.*?\]', ligne_fr_entiere)
        # strip all
        ligne_fr_split = [ligne.strip() for ligne in ligne_fr_split]
        # remove empty lines
        ligne_fr_split = [ligne for ligne in ligne_fr_split if ligne != ""]

        if len(ligne_fr_split) > 1:
            if isFirstLine:
                return ligne_fr_split[0].strip()
            else:
                ligne_precedente = script_fr_mem[i - 1].strip()

                # on cherche l'indice de la ligne précédente dans la ligne split
                indice_ligne_precedente = ligne_fr_split.index(ligne_precedente) if ligne_precedente in ligne_fr_split else None
                # si on trouve l'indice, on prend la ligne suivante
                if indice_ligne_precedente is not None and indice_ligne_precedente + 1 < len(ligne_fr_split):
                    return ligne_fr_split[indice_ligne_precedente + 1].strip()

    return None

def recupere_ligne_traduite(lignes_fr: list[str], indice: int):
    if indice < len(lignes_fr):
        return lignes_fr[indice].strip()
    
    return None

def creer_fichier_steam(lignes_script: list[str], script_sortie: str):
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
                idx_fichier = 0
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
                # si la ligne n'est pas trouvée, on cherche si elle est incluse dans une autre ligne
                ligne_partielle = trouver_fr_partiel(idx, lignes_og, lignes_fr)
                if ligne_partielle is not None:
                    nbStartSpaces = len(ligne) - len(ligne.lstrip())
                    remplace_dans_script(idx, ligne_partielle, nbStartSpaces)
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