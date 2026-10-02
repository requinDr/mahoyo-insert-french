"""Generates the translated images whose text is drawn by code (images shared by all
languages, where the English band is replaced), from the texts in
sources/image-texts.json and the original images read from the game (config.ini).

Every section of the JSON is an edit: {image: what to write}, the image being the number
of an image shared by all languages (imgNNNN) or the name of an English one (name_en.cbg).
EDITS gives the function applied to each image of the section; a new kind of edit is a
function `edit(image: GameImage, config)` that redraws image.target, added to EDITS.

Usage: python generate_images.py [section…]   (all sections by default)
The PNGs are written to sources/assets-fr; run main.py afterwards.
"""
import json
import sys
from pathlib import Path

import utils.config_importer as conf
from utils.images import backgrounds, captions, chapter_titles, map_labels, ploy, text_boxes
from utils.images.game import GameImage

TEXTS = 'sources/image-texts.json'
EDITS = {
	'text_boxes': text_boxes.text_boxes,
	'chapter_titles': chapter_titles.chapter_title,
	'map_labels': map_labels.map_labels,
	'ploy_titles': ploy.title,
	'ploy_sheets': ploy.sheet,
	'ploy_captions': ploy.caption,
	'warning': backgrounds.warning,
	'apology': backgrounds.apology,
	'speech_bubbles': backgrounds.speech_bubble,
	'deduction_captions': captions.glow_caption,
	'quote': captions.quote,
	'outlined_blocks': captions.outlined_blocks,
}


def main(sections: list[str]):
	with open(TEXTS, encoding='utf-8') as f:
		texts = {key: value for key, value in json.load(f).items() if not key.startswith('_')}
	unknown = [s for s in sections + list(texts) if s not in EDITS]
	if unknown:
		sys.exit(f"Section inconnue : {', '.join(unknown)} (choix : {', '.join(EDITS)})")
	out_dir = Path(conf.images_folder)
	written = []
	for section in sections:
		for key, config in texts.get(section, {}).items():
			image = GameImage(key)
			EDITS[section](image, config)
			image.save(out_dir)
			written.append(image.file_name)
	print(f"{len(written)} images écrites dans {out_dir} : {', '.join(written)}")


if __name__ == '__main__':
	main(sys.argv[1:] or list(EDITS))
