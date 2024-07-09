import os
import shutil
import time

import utils.config_importer as conf
from utils.translation.translate_csv import read_csv_from_name
from utils.translation.process_translation import generate_updated_translation
from utils.utils import CLEAN_END, get_file_lines, write_file_lines, progress
from utils.steam.translate_swap import swap_char_in_script, swap_char_in_line
from utils.switch.utils import extract_switch_line_offset
import utils.converters.HunexFileArchiveTool.hunex_file_archive_tool as hfa

def create_steam_exe_titles_file(file: str):
	lines = read_csv_from_name(file)
	for line in lines:
		line[2] = swap_char_in_line(line[2])

	# make lines a normal list of strings however many columns
	new_lines = []
	for line in lines:
		new_lines.append(','.join(line))
		new_lines.append("\n")

	if new_lines[-1] != "\n":
		new_lines.append("\n")

	write_file_lines("output-steam/TEXT5.bin", new_lines)

def create_steam_file(new_lines: list[str]):
	progress(0, 100, "Steam\t")

	lines_to_write = new_lines
	
	if conf.remplacer_caracteres:
		lines_to_write = swap_char_in_script(new_lines.copy())
		write_file_lines("generated/swapped.txt", lines_to_write)
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

	if os.path.exists(conf.exe_titles_file):
		create_steam_exe_titles_file(conf.exe_titles_file)
	
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


if __name__ == "__main__":
	debut = time.time()

	new_lines = generate_updated_translation()
	create_steam_file(new_lines)
	# update_switch_files(new_lines)
	
	fin = time.time()
	temps_execution = fin - debut
	print(f"\nTerminé en {temps_execution:.2f} secondes !")