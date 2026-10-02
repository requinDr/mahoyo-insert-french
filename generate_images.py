"""Generates the translated images whose text is drawn by code (images shared by all
languages, where the English band is replaced), from the texts in
sources/image-texts.json and the original images read from the game (config.ini).

Usage: python generate_images.py [titles] [sheets] [backgrounds] [captions]   (all by default)
The PNGs are written to sources/assets-fr; run main.py afterwards.
"""
import json
import sys
from pathlib import Path

import utils.config_importer as conf
from utils.images import glow_captions, ploy_sheets, ploy_titles, text_backgrounds

TEXTS = 'sources/image-texts.json'
GROUPS = ('titles', 'sheets', 'backgrounds', 'captions')


def main(groups: list[str]):
	unknown = [g for g in groups if g not in GROUPS]
	if unknown:
		sys.exit(f"Groupe inconnu : {', '.join(unknown)} (choix : {', '.join(GROUPS)})")
	with open(TEXTS, encoding='utf-8') as f:
		texts = json.load(f)
	out_dir = Path(conf.images_folder)
	written = []
	if 'titles' in groups:
		written += ploy_titles.generate(texts['ploy_titles'], out_dir)
	if 'sheets' in groups:
		written += ploy_sheets.generate(texts['ploy_sheets'], texts['ploy_captions'], out_dir)
	if 'backgrounds' in groups:
		written.append(text_backgrounds.warning(texts['warning'], out_dir))
		written.append(text_backgrounds.apology(texts['apology'], out_dir))
	if 'captions' in groups:
		written += glow_captions.captions(texts['deduction_captions'], out_dir)
		written.append(glow_captions.quote(texts['quote'], out_dir))
	print(f"{len(written)} images écrites dans {out_dir} : {', '.join(written)}")


if __name__ == '__main__':
	main(sys.argv[1:] or list(GROUPS))
