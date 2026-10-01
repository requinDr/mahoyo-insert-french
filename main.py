import time

import utils.config_importer as conf
from utils.translation.process_translation import generate_updated_translation
from utils.utils import CLEAN_END
from utils.steam.build_patch import build_patch

def create_steam_patch(new_lines: list[str]):
	print(f"Création du patch Steam...{CLEAN_END}", flush=True, end="\r")
	zip_path = build_patch(new_lines, conf.exe_titles_file, conf.images_folder, conf.fonts_folder, conf.readme,
		conf.game_folder, conf.output_folder, conf.patch_name)
	print(f"Patch Steam créé : {zip_path}{CLEAN_END}")


if __name__ == "__main__":
	debut = time.time()

	new_lines = generate_updated_translation()
	create_steam_patch(new_lines)
	
	fin = time.time()
	temps_execution = fin - debut
	print(f"\nTerminé en {temps_execution:.2f} secondes !")