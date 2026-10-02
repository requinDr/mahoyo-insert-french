import configparser
import os

filename = 'config.ini'

dossier_sources_jp = 'sources/sources-jp'
dossier_sources_fr = 'sources/sources-fr'
script_source = 'sources/script_text_ja.txt'
script_source_indent = 'sources/script_text_en.txt'
# Lignes non trouvées ou à corriger (numéros de ligne à partir de 1)
csv_input = 'sources/lignes_modifiees.csv'
# Remplacements appliqués en dernier sur tout le script (\uXXXX accepté pour les caractères invisibles)
replacements_csv = 'sources/remplacements.csv'
exe_titles_file = 'sources/TEXT5.csv'  # textes système : clé, ja, fr, zc, zt
images_folder = 'sources/assets-fr'  # images françaises en PNG
fonts_folder = 'sources/fonts-fr'  # polices françaises (.mzp, .ccit)
readme = 'sources/LISEZMOI.txt'
generated_translation = 'generated/script_text_fr.txt'
csv_output = 'generated/lignes_modifiees.csv'
output_folder = 'dist'
patch_name = 'WOTHN patch fr'

try:
	if not os.path.isfile(filename):
		raise FileNotFoundError(f"Le fichier {filename} est introuvable.")

	config = configparser.ConfigParser()
	with open(filename, encoding="utf-8") as f:
		config.read_string("[config]\n" + f.read())

	game_folder = config['config']['game_folder']
	creer_csv = config.getboolean('config', 'create_csv')
except Exception as e:
	print(f"Erreur lors de l'importation du fichier de configuration :\n{e}")
	exit(1)
