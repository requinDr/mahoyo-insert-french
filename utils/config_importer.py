import configparser
import os

class Config:
	def __init__(self, filename='config.ini'):
		if not os.path.isfile(filename):
			raise FileNotFoundError(f"Le fichier {filename} est introuvable.")
		
		self.config = configparser.ConfigParser()
		self.config.read(filename)

		self.script_source = self.config['paths']['script_source']
		self.script_source_indent = self.config['paths']['script_source_indent']
		self.dossier_sources_jp = self.config['paths']['dossier_sources_jp']
		self.dossier_sources_fr = self.config['paths']['dossier_sources_fr']
		self.generated_translation = self.config['paths']['generated_translation']
		self.csv_input = self.config['csv']['source']
		self.csv_output = self.config['csv']['generated']
		self.creer_csv = self.config.getboolean('csv', 'create_csv')
		self.output_steam_patch_folder = self.config['steam']['output_steam_patch_folder']
		self.input_steam_patch_folder = self.config['steam']['input_steam_patch_folder']
		self.steam_hfa_name = self.config['steam']['steam_hfa_name']
		self.remplacer_caracteres = self.config.getboolean('steam', 'swap_characters')
		self.output_switch_folder = self.config['switch']['output_folder']

	# update ini file
	def update(self):
		try:
			with open('config.ini', 'w') as configfile:

				self.config['paths']['script_source'] = self.script_source
				self.config['paths']['script_source_indent'] = self.script_source_indent
				self.config['paths']['dossier_sources_jp'] = self.dossier_sources_jp
				self.config['paths']['dossier_sources_fr'] = self.dossier_sources_fr
				self.config['paths']['generated_translation'] = self.generated_translation
				self.config['csv']['source'] = self.csv_input
				self.config['csv']['generated'] = self.csv_output
				self.config['csv']['create_csv'] = str(self.creer_csv)
				self.config['steam']['output_steam_patch_folder'] = self.output_steam_patch_folder
				self.config['steam']['input_steam_patch_folder'] = self.input_steam_patch_folder
				self.config['steam']['steam_hfa_name'] = self.steam_hfa_name
				self.config['steam']['swap_characters'] = str(self.remplacer_caracteres)
				self.config['switch']['output_folder'] = self.output_switch_folder

				self.config.write(configfile)
		except Exception as e:
			raise e

# Créer une instance de la configuration globale
config = Config()