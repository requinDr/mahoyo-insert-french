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
  ja, en, zc, zt), dont seule la bande anglaise traduite est stockée ; le build la remet
  dans l'image d'origine et n'en garde que les tuiles modifiées. Elles gardent leur nom
  d'origine : `version.dll` reconstruit l'image et redirige l'entrée du jeu vers elle.
- `sources/fonts-fr` : polices françaises (atlas `FONT_fr_*.mzp`, tables `Font040*.ccit`).

## Images au texte dessiné

Une partie des images `imgNNNN.png` est produite par programme. Le texte vient de
`sources/image-texts.json`, et l'image d'origine est lue directement dans le jeu :

- écran d'avertissement (`caution`), onglets des paramètres (`btn_base0`) et boutons « Retour » / « Lire » des archives (`archive_return`, `archive_read`) ;
- aide des commandes et panneaux d'options (`conf_manual1`, `panel1`, `panel3`, `panel4`, à partir des images `_en`) ;
- choix des options « Bas / Haut » et « Lent / Rapide » (`conf_stxt01`, `conf_stxt2`) ;
- titres de chapitre (img0409-0422) ;
- plan du parc (img1372-1375, img1378-1379, img2393-2395) ;
- logos « Tout sur les Ploy » (img2111-2112, img2174-2175) ;
- titres, fiches et miniatures d'archive Ploy (img2167-2172, img2258-2268, nz1-nz6) ;
- avertissement avant le chapitre bonus (img1955) et écran d'excuses (img2256) ;
- noms de chapitre et bouton « Retour » des archives (`archive_010` à `archive_130`, `archive_back`) ;
- légendes de déduction (img1961-1968) et citation de Tokki (img1924) ;
- titre d'émission « Animal Land Terror » (img2397) et bulle « Au travail ! » (img2091).

Après une modification des textes :

```powershell
python generate_images.py           # ou seulement certaines sections : python generate_images.py chapter_titles map_labels
python main.py
```

Positions, tailles et couleurs sont calquées sur l'anglais, seul le texte change.
Les polices ne sont pas fournies (licences) : celles de `FONTS` (`utils/images/fonts.py`)
sont cherchées dans les polices du système ou dans `sources/polices-images/` (ignoré par git).

Organisation de `utils/images/` :

- `game.py` : `GameImage`, image d'origine lue dans le jeu, dont on redessine la bande anglaise (`target`),
  ou l'image entière pour une image anglaise (`nom_en.cbg`, enregistrée en `nom_fr.png`) ;
- `text.py` : tracé des lignes et mesures du texte anglais (hauteur, ligne de base, espacement) ;
- `effects.py` : halo, ombre, contour (mesurés sur l'anglais) et superposition ;
- `inpaint.py` : effacement du texte anglais (autres bandes, motif répété, lignes prolongées) ;
- un module par famille d'images : `chapter_titles`, `map_labels`, `ploy`, `ploy_arc_titles`, `backgrounds`, `captions`, `buttons`,
  et `text_boxes` (lignes remplacées une à une dans des zones, pour les menus et pages d'aide).

Chaque section du JSON est une édition `{image: texte}` (numéro d'image commune, ou nom d'image anglaise) ; `EDITS` (`generate_images.py`)
associe à chaque section une fonction `edit(image, config)` qui redessine `image.target`.
Ajouter un type d'édition : écrire cette fonction, l'ajouter à `EDITS` et créer sa section.

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