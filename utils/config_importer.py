import configparser
import os

filename = 'config.ini'

try:
	if not os.path.isfile(filename):
		raise FileNotFoundError(f"Le fichier {filename} est introuvable.")

	config = configparser.ConfigParser()
	config.read(filename)

	script_source = config['paths']['script_source']
	script_source_indent = config['paths']['script_source_indent']
	dossier_sources_jp = config['paths']['dossier_sources_jp']
	dossier_sources_fr = config['paths']['dossier_sources_fr']
	generated_translation = config['paths']['generated_translation']
	csv_input = config['csv']['csv_input']
	csv_output = config['csv']['csv_output']
	creer_csv = config.getboolean('csv', 'create_csv')
	output_steam_patch_folder = config['steam']['output_steam_patch_folder']
	input_steam_patch_folder = config['steam']['input_steam_patch_folder']
	steam_hfa_name = config['steam']['steam_hfa_name']
	remplacer_caracteres = config.getboolean('steam', 'swap_characters')
	output_switch_folder = config['switch']['output_switch_folder']
except Exception as e:
	print(f"Erreur lors de l'importation du fichier de configuration :\n{e}")
	exit(1)

