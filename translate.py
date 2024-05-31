import os
import shutil
from sys import platform
import time
import eel

from py_src.contrib.replace_in_file import findFileRe, replaceInfile
import utils.config_importer as conf
from utils.translation.translation import generate_updated_translation
from utils.utils import CLEAN_END, get_file_lines, write_file_lines, progress
from utils.steam.translate_swap import swap_char_in_script
from utils.switch.utils import extract_switch_line_offset
import utils.converters.HunexFileArchiveTool.hunex_file_archive_tool as hfa

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


# if __name__ == "__main__":
# 	debut = time.time()

# 	new_lines = generate_updated_translation()
# 	create_steam_file(new_lines)
# 	update_switch_files(new_lines)
	
# 	fin = time.time()
# 	temps_execution = fin - debut
# 	print(f"\nTerminé en {temps_execution:.2f} secondes !")
# eel.init('web_src')
@eel.expose
def generate_translation():
	debut = time.time()

	new_lines = generate_updated_translation()
	create_steam_file(new_lines)
	update_switch_files(new_lines)
	
	fin = time.time()
	temps_execution = fin - debut
	print(f"\nTerminé en {temps_execution:.2f} secondes !")

# eel.start('index.html', size=(800, 600))

def start_eel(develop):
    """Start Eel with either production or development configuration."""

    if develop:
        directory = 'web_src'
        app = None
        page = {'port': 5173}
        eel_port = 5169
    else:
        directory = 'dist_vite'
        app = 'chrome'
        page = 'index.html'

        # find a unused port to host the eel server/websocket
        # eel_port = find_unused_port()

        # replace the port in the web files
        replace_file = findFileRe("./dist_vite/assets", "index.*.js")
        replaceInfile(f"./dist_vite/assets/{replace_file}", 'ws://localhost:....', f"ws://localhost:{eel_port}")
        replaceInfile("./dist_vite/index.html", 'http://localhost:.....eel.js', f"http://localhost:{eel_port}/eel.js")



    eel.init(directory, ['.tsx', '.ts', '.jsx', '.js', '.html'])

    # These will be queued until the first connection is made, but won't be repeated on a page reload
    # say_hello_py('Python World!')
    # eel.say_hello_js('Python World!')   # Call a JavaScript function (must be after `eel.init()`)

    # eel.show_log('https://github.com/samuelhwilliams/Eel/issues/363 (show_log)')

    eel_kwargs = dict(
        host='localhost',
        port=eel_port,
        size=(1280, 800),
    )
    try:
        eel.start(page, mode=app, **eel_kwargs)

    except EnvironmentError:
        # If Chrome isn't found, fallback to Microsoft Edge on Win10 or greater
        if sys.platform in ['win32', 'win64'] and int(platform.release()) >= 10:
            eel.start(page, mode='edge', **eel_kwargs)
        else:
            raise


if __name__ == '__main__':
    import sys

    # Pass any second argument to enable debugging
    start_eel(develop=len(sys.argv) == 2)