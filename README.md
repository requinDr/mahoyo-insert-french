Script de portage de la traduction Kirikiri vers le remaster Steam de Mahoyo (WITCH ON THE HOLY NIGHT).

## Générer le patch

Prérequis : Python 3.10+ et le jeu Steam installé (chemin dans `config.ini`).

```powershell
pip install -r requirements.txt
python main.py
```

Résultat dans `dist/` :

- `dist/WOTHN patch fr/` : les fichiers à copier dans le dossier du jeu
- `dist/WOTHN patch fr.zip` : même contenu

Le patch contient seulement deux fichiers ajoutés au dossier du jeu (aucun fichier
Steam n'est remplacé) et un `LISEZMOI.txt` pour les joueurs :

| Fichier | Rôle |
|---|---|
| `data00999.hfa` | Archive française : `script_text_fr.ctd`, images `*_fr.cbg`, polices `FONT_fr_*` / `Font040*`, textes système `TEXT5_fr.csv`. Le jeu charge automatiquement tout `data0????.hfa`. |
| `version.dll` | Chargée automatiquement par `WoH.exe`. Redirige en mémoire les ressources anglaises vers les françaises, fournit les textes système, corrige les retours à la ligne au milieu des mots accentués et ajoute « - Patch FR » au titre de la fenêtre. |

Pour désinstaller : supprimer ces deux fichiers.

Sous Linux / Steam Deck, Proton ignore une `version.dll` placée dans le dossier du jeu : il faut
l'option de lancement Steam `WINEDLLOVERRIDES="version=n,b" %command%` (expliqué dans le LISEZMOI).

## Sources

- `sources/sources-fr`, `sources/sources-jp`, `sources/*.txt`, `sources/lignes_modifiees.csv` : traduction et alignement.
- `sources/TEXT5.csv` : textes système (colonnes clé, ja, fr, zc, zt).
- `sources/assets-fr` : images françaises en PNG, nommées comme les ressources
  anglaises du jeu (`_en` → `_fr`), converties automatiquement en `.cbg` à la
  génération. Une image doit garder les dimensions et la disposition de l'originale
  (états normal/survolé…).
- `sources/assets-fr/imgNNNN.png` : images communes à toutes les langues (4 bandes :
  ja, en, zc, zt), dont la bande anglaise est traduite. Elles gardent leur nom d'origine :
  `version.dll` redirige l'entrée du jeu vers la version de `data00999.hfa`.
- `sources/fonts-fr` : polices françaises (atlas `FONT_fr_*.mzp`, tables `Font040*.ccit`).

## Images au texte dessiné

Une partie des images `imgNNNN.png` est produite par programme. Le texte vient de
`sources/image-texts.json`, et l'image d'origine est lue directement dans le jeu :

- titres de chapitre (img0409-0422) ;
- plan du parc (img1372-1375, img1378-1379, img2393-2395) ;
- titres et fiches Ploy (img2167-2172, img2258-2268) ;
- avertissement avant le chapitre bonus (img1955) et écran d'excuses (img2256) ;
- légendes de déduction (img1961-1968) et citation de Tokki (img1924) ;
- titre d'émission « Animal Land Terror » (img2397) et bulle « Au travail ! » (img2091).

Après une modification des textes :

```powershell
python generate_images.py           # ou : python generate_images.py chapters maps titles sheets backgrounds captions
python main.py
```

Positions, tailles, couleurs sont calquées sur l'anglais, seul le texte change,
Les polices ne sont pas fournies (licences) : Arial Rounded MT Bold, Segoe Print, Palatino Linotype
et Helvetica Neue sont cherchées dans les polices du système ou dans `sources/polices-images/` (ignoré par git).
- `native/version.c` : code de la DLL. `native/version.dll` est la version compilée,
  copiée telle quelle dans le patch : elle ne dépend pas de la traduction et n'est à
  recompiler qu'après une modification de `version.c` (ou de `shared_names`), avec
  `python native/build_dll.py` (nécessite Visual Studio avec les outils C++).

## Limites

- Le français remplace l'anglais
  affiche « Français » à sa place (`modfr.cbg`, remplaçant `mode1.cbg`).

## Crédits

- Traduction française : [mahoyo-french](https://github.com/IDerr/mahoyo-french)
- loicfr, pour son travail sur les outils du remaster et l'ajout de glyphes aux polices : [mahoyo_tools](https://github.com/loicfrance/mahoyo_tools)
- requindr, pour le portage des scripts et l'édition d'images
- Valkujo, pour l'édition d'images
- Claude by Anthropic, pour l'écriture du code de la DLL