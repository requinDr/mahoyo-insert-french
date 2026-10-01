"""Positions des particules qui encadrent l'entrée survolée des menus titre et Extra.

Le moteur les lit dans des tables de .rdata : pour chaque entrée, (gauche, droite, y)
en pixels écran, calées sur la largeur des textes anglais. On les recalcule d'après
la largeur des textes dans les images françaises, et version.dll applique le résultat
(fichier rdata_fr.bin de l'archive).
"""
import struct
from pathlib import Path

import numpy as np
from PIL import Image

DATA_PATCHES_ENTRY = "rdata_fr.bin"  # nom attendu par native/version.c

MENUS = [
	dict(
		image="title_menu_fr.png",
		cell=(496, 88),           # taille d'une entrée dans l'image (état normal en haut à gauche)
		rows=[2, 0, 1, 3, 4, 5],  # ligne de l'image de chaque entrée, dans l'ordre de la table
		table=[(784, 1088, 484), (840, 1032, 572), (696, 1176, 660),
			(816, 1056, 748), (828, 1044, 836), (840, 1032, 924)],
		text_center=248,          # centre des textes anglais dans une cellule
		margin=33,                # écart entre le texte et les particules, comme en anglais
	),
	dict(
		image="extra_menu_fr.png",
		cell=(612, 106),
		rows=[0, 1, 2, 3],
		table=[(760, 1100, 484), (760, 1100, 590), (700, 1160, 696), (820, 1040, 802)],
		text_center=304,
		margin=34,
	),
]


def _pack(table: list[tuple[int, int, int]]) -> bytes:
	return b"".join(struct.pack("<3i", *entry) for entry in table)


def data_patches(images_dir: str) -> bytes:
	out = b""
	for menu in MENUS:
		path = Path(images_dir) / menu["image"]
		if not path.exists():
			continue
		with Image.open(path) as image:
			alpha = np.array(image.convert("RGBA"))[:, :, 3]
		width, height = menu["cell"]
		new_table = []
		for row, (left, right, y) in zip(menu["rows"], menu["table"]):
			columns = np.flatnonzero((alpha[row * height:(row + 1) * height, :width] > 200).any(axis=0))
			text_left, text_right = columns.min(), columns.max()
			center = (left + right) / 2 + (text_left + text_right) / 2 - menu["text_center"]
			half = (text_right - text_left) / 2 + menu["margin"]
			new_table.append((round(center - half), round(center + half), y))
		before, after = _pack(menu["table"]), _pack(new_table)
		out += struct.pack("<I", len(before)) + before + after
	return out
