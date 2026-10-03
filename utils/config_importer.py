import configparser
import os
import sys

CONFIG_FILE = 'config.ini'

jp_sources_folder = 'sources/sources-jp'
fr_sources_folder = 'sources/sources-fr'
script_source = 'sources/script_text_ja.txt'
script_source_indent = 'sources/script_text_en.txt'
# Lines missing from the sources or corrected (line numbers start at 1)
csv_input = 'sources/lignes_modifiees.csv'
# Replacements applied last to the whole script (\uXXXX accepted for invisible characters)
replacements_csv = 'sources/remplacements.csv'
exe_titles_file = 'sources/TEXT5.csv'  # system texts: key, ja, fr, zc, zt
images_folder = 'sources/assets-fr'
fonts_folder = 'sources/fonts-fr'
readme = 'sources/LISEZMOI.txt'
generated_translation = 'generated/script_text_fr.txt'
csv_output = 'generated/lignes_modifiees.csv'
output_folder = 'dist'
patch_name = 'WOTHN patch fr'

try:
	if not os.path.isfile(CONFIG_FILE):
		raise FileNotFoundError(f"{CONFIG_FILE} not found")
	config = configparser.ConfigParser()
	with open(CONFIG_FILE, encoding="utf-8") as f:
		config.read_string("[config]\n" + f.read())
	game_folder = config['config']['game_folder']
	create_csv = config.getboolean('config', 'create_csv')
except Exception as e:
	sys.exit(f"Cannot read {CONFIG_FILE}:\n{e}")
