import time

import utils.config_importer as conf
from utils.translation.process_translation import generate_updated_translation
from utils.utils import CLEAN_END
from utils.steam.build_patch import build_patch


def create_steam_patch(lines: list[str]):
	print(f"Building the Steam patch...{CLEAN_END}", flush=True, end="\r")
	zip_path = build_patch(lines, conf.exe_titles_file, conf.images_folder, conf.fonts_folder, conf.readme,
		conf.game_folder, conf.output_folder, conf.patch_name)
	print(f"Steam patch built: {zip_path}{CLEAN_END}")


if __name__ == "__main__":
	start = time.time()
	create_steam_patch(generate_updated_translation())
	print(f"\nDone in {time.time() - start:.2f} s")
