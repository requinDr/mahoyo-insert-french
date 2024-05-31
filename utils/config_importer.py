import pickle
import os

steam_hfa_name = "data00200"

conf_file = "config.pkl"
conf_default = {
	"ks_source": "sources/sources-jp",
	"ks_translated": "sources/sources-fr",
	"script_source": "sources/script_text_ja.txt",
	"script_source_indent": "sources/script_text_en.txt",
	"generated_translation": "generated/script_text_fr.txt",
	"csv": {
		"source": "sources/lignes_modifiees.csv",
		"generated": "sources/lignes_modifiees_new.csv",
		"create_csv": False
	},
	"steam": {
		"hfa_name": "patch",
		"source_folder": "C:\Program Files (x86)\Steam\steamapps\common\WITCH ON THE HOLY NIGHT",
		"output_folder": "C:\Program Files (x86)\Steam\steamapps\common\WITCH ON THE HOLY NIGHT",
		"swap_characters": True
	},
	"switch": {
		"output_folder": "output-switch"
	}
}

class Config(object):
	def __init__(self):
		try:
			if os.path.exists(conf_file):
				with open(conf_file, 'rb') as f:
					conf = pickle.load(f)
					self.update_self(conf)
			else:
				self.update_self(conf_default)

				with open(conf_file, 'wb') as f:
					pickle.dump(self, f)
		except Exception as e:
			print(f"Erreur lors de la lecture du fichier de configuration: {e}")

	def update_self(self, conf):
		self.ks_source = conf["ks_source"]
		self.ks_translated = conf["ks_translated"]
		self.script_source = conf["script_source"]
		self.script_source_indent = conf["script_source_indent"]
		self.generated_translation = conf["generated_translation"]
		self.csv = conf["csv"]
		self.steam = conf["steam"]
		self.switch = conf["switch"]

	def update(self, config):
		self.update_self(config)
		with open(conf_file, 'wb') as f:
			pickle.dump(config, f)


config = Config()