import os
import shutil
import time
import eel

from utils.config_importer import config as conf
from utils.translation.translation import generate_updated_translation
from utils.utils import CLEAN_END, get_file_lines, write_file_lines, progress
from utils.steam.translate_swap import swap_char_in_script
from utils.switch.utils import extract_switch_line_offset
import utils.converters.HunexFileArchiveTool.hunex_file_archive_tool as hfa

@eel.expose
def get_config():
	eel.update_conf_js({
		"ks_source": conf.dossier_sources_jp,
		"ks_translated": conf.dossier_sources_fr,
		"script_source": conf.script_source,
		"script_source_indent": conf.script_source_indent,

		"csv": {
			"source": conf.csv_input,
			"generated": conf.csv_output,
			"create_csv": conf.creer_csv
		},

		"steam": {
			"hfa_name": conf.steam_hfa_name,
			"source_folder": conf.input_steam_patch_folder,
			"output_folder": conf.output_steam_patch_folder,
			"swap_characters": conf.remplacer_caracteres
		},

		"switch": {
			"output_folder": conf.output_switch_folder
		}
	})

def init_translate():
	get_config()
	return

def create_steam_file(new_lines: list[str]):
	progress(0, 100, "Steam\t")
	
	lines_to_write = swap_char_in_script(new_lines.copy()) if conf.remplacer_caracteres else new_lines
	progress(20, 100, "Steam\t")

	success = hfa.extract(f"{conf.input_steam_patch_folder}/{conf.steam_hfa_name}.hfa")
	if not success:
		print(f"Erreur lors de l'extraction du patch Steam{CLEAN_END}", end="\n")
		return
	progress(40, 100, "Steam\t")

	write_file_lines(f"{conf.steam_hfa_name}/0000_script_text_en.ctd", lines_to_write)
	progress(60, 100, "Steam\t")

	success = hfa.build(conf.steam_hfa_name, f"{conf.steam_hfa_name}.hfa", conf.output_steam_patch_folder)
	progress(80, 100, "Steam\t")

	if os.path.exists(conf.steam_hfa_name):
		shutil.rmtree(conf.steam_hfa_name, ignore_errors=True)
	
	if not success:
		print(f"Erreur lors de la création du patch Steam{CLEAN_END}", end="\n")
		return
	progress(100, 100, "Steam\t")

	print(f"Patch Steam créé : {conf.steam_hfa_name}.hfa{CLEAN_END}", end="\n")


def update_switch_files(new_lines: list[str]):
	files = os.listdir(conf.output_switch_folder)
	total_files = len(files)

	for idx, file in enumerate(files):
		progress(idx, total_files - 1, "Switch\t")

		file_path = os.path.join(conf.output_switch_folder, file)
		lines = get_file_lines(file_path)

		for i in range(len(lines)):
			if lines[i].startswith("[sha:"):
				offset = extract_switch_line_offset(lines[i + 1])
				if offset is not None:
					# on remplace la ligne par la traduction
					lines[i + 3] = new_lines[offset]

		write_file_lines(file_path, lines)

	print(f"Fichiers Switch pour deepLuna mis à jour dans {conf.output_switch_folder}", end="\n")


@eel.expose
def generate_translation():
	debut = time.time()

	new_lines = generate_updated_translation()
	create_steam_file(new_lines)
	update_switch_files(new_lines)
	
	fin = time.time()
	temps_execution = fin - debut
	print(f"\nTerminé en {temps_execution:.2f} secondes !")

if __name__ == "__main__":
	generate_translation()