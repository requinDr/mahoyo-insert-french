# Images .mzp (archive « mrgd00 » de tuiles HEP compressées en MZX) du remaster Steam
#
# Format :
#  - archive mrgd00 : en-tête, table [secteur, décalage, nb secteurs, taille & 0xFFFF]
#    (secteurs de 0x800 octets), puis les entrées alignées sur 8 octets ;
#  - entrée 0 : largeur, hauteur, taille des tuiles, nombre de tuiles, type, rognage ;
#  - entrées suivantes : une tuile chacune, compressée en MZX. Une tuile HEP contient
#    un en-tête, un octet d'indice de palette par pixel et une palette RGBA de 256
#    couleurs (alpha sur 7 bits). Chaque tuile déborde d'un pixel (rognage) sur ses
#    voisines.
#
# Seules les tuiles dont les pixels changent sont réencodées, les autres sont
# reprises telles quelles du fichier d'origine.
import struct

import numpy as np
from PIL import Image

MAGIC = b"mrgd00"
SECTOR = 0x800
ALIGN = 8
MZX_MAGIC = b"MZX0"
HEP_HEADER_SIZE = 0x20
HEP_TYPE = 0x0C


def _read_entries(data: bytes) -> list[bytes]:
	if data[:6] != MAGIC:
		raise ValueError("fichier .mzp invalide")
	count, = struct.unpack_from("<H", data, 6)
	start = 8 + count * 8
	entries = []
	for i in range(count):
		sector, offset, sectors, low_size = struct.unpack_from("<4H", data, 8 + i * 8)
		position = sector * SECTOR + offset
		size = low_size
		while (position + size + SECTOR - 1) // SECTOR - position // SECTOR < sectors:
			size += SECTOR
		entries.append(data[start + position:start + position + size])
	return entries


def _write_entries(entries: list[bytes]) -> bytes:
	table = bytearray(MAGIC + struct.pack("<H", len(entries)))
	content = bytearray()
	for entry in entries:
		position = len(content)
		sectors = (position + len(entry) + SECTOR - 1) // SECTOR - position // SECTOR
		table += struct.pack("<4H", position // SECTOR, position % SECTOR, sectors, len(entry) & 0xFFFF)
		content += entry + b"\xff" * (ALIGN - len(entry) % ALIGN)
	return bytes(table + content)


def _mzx_decompress(data: bytes) -> bytes:
	if data[:4] != MZX_MAGIC:
		raise ValueError("tuile MZX invalide")
	size, = struct.unpack_from("<I", data, 4)
	out = bytearray()
	ring = bytearray(128)
	ring_position = 0
	clear_count = 0
	i = 8
	while len(out) < size and i < len(data):
		flags = data[i]
		i += 1
		command, argument = flags & 3, flags >> 2
		if clear_count <= 0:
			clear_count = 0x1000
		if command == 0:  # répète le dernier mot (zéro au début d'un bloc)
			last = b"\0\0" if clear_count == 0x1000 else out[-2:]
			out += last * (argument + 1)
		elif command == 1:  # copie depuis plus haut
			distance = 2 * (data[i] + 1)
			i += 1
			for _ in range(2 * (argument + 1)):
				out.append(out[-distance])
		elif command == 2:  # mot du tampon circulaire
			out += ring[argument * 2:argument * 2 + 2]
		else:  # mots littéraux
			chunk = data[i:i + (argument + 1) * 2]
			i += len(chunk)
			out += chunk
			for byte in chunk:
				ring[ring_position] = byte
				ring_position = (ring_position + 1) % len(ring)
		clear_count -= 1 if command == 2 else argument + 1
	return bytes(out[:size])


def _mzx_compress(data: bytes) -> bytes:
	"""Mots littéraux et répétitions du mot précédent (suffisant pour des images à aplats)."""
	words = np.frombuffer(data + b"\0" * (len(data) % 2), dtype="<u2")
	out = bytearray(MZX_MAGIC + struct.pack("<I", len(data)))
	clear_count = 0
	cursor = 0
	while cursor < len(words):
		if clear_count <= 0:
			clear_count = 0x1000
		# Le décodeur répète zéro (et non le mot précédent) au début de chaque bloc de 0x1000 mots
		last = 0 if clear_count == 0x1000 else (words[cursor - 1] if cursor else None)
		run = 0
		while last is not None and run < 64 and cursor + run < len(words) and words[cursor + run] == last:
			run += 1
		if run >= 2:
			out.append((run - 1) << 2)
			count = run
		else:
			# littéraux jusqu'à la prochaine répétition d'au moins 3 mots
			count = 1
			while count < 64 and cursor + count < len(words):
				w = words[cursor + count - 1:cursor + count + 2]
				if len(w) == 3 and w[0] == w[1] == w[2]:
					break
				count += 1
			out.append(3 | (count - 1) << 2)
			out += words[cursor:cursor + count].tobytes()
		cursor += count
		clear_count -= count
	return bytes(out)


def _hep_decode(tile: bytes, width: int, height: int) -> np.ndarray:
	count = width * height
	palette = np.frombuffer(tile, np.uint8, 1024, HEP_HEADER_SIZE + count).reshape(256, 4).copy()
	alpha = palette[:, 3].astype(np.uint16)
	palette[:, 3] = np.where(alpha & 0x80, 255, ((alpha << 1) | (alpha >> 6)) & 0xFF)
	indices = np.frombuffer(tile, np.uint8, count, HEP_HEADER_SIZE)
	return palette[indices].reshape(height, width, 4)


def _hep_encode(header: bytes, pixels: np.ndarray) -> bytes:
	height, width = pixels.shape[:2]
	flat = pixels.reshape(-1, 4).copy()
	flat[flat[:, 3] == 0] = 0  # couleur des pixels transparents indifférente
	colors, indices = np.unique(flat, axis=0, return_inverse=True)
	if len(colors) > 256:
		quantized = Image.fromarray(pixels).quantize(256, Image.Quantize.FASTOCTREE)
		colors = np.array(quantized.getpalette("RGBA")[:1024], np.uint8).reshape(-1, 4)
		indices = np.array(quantized).ravel()
	palette = np.zeros((256, 4), np.uint8)
	palette[:len(colors)] = colors
	palette[:, 3] = np.where(palette[:, 3] == 255, 255, palette[:, 3] >> 1)
	return header[:HEP_HEADER_SIZE] + indices.astype(np.uint8).tobytes() + palette.tobytes()


def encode_mzp(original: bytes, image: Image.Image) -> bytes:
	"""Remplace les pixels de l'image .mzp d'origine par ceux de image (mêmes dimensions)."""
	entries = _read_entries(original)
	width, height, tile_width, tile_height, columns, rows, kind, _, crop = struct.unpack_from("<7H2B", entries[0])
	if kind != HEP_TYPE:
		raise ValueError(f"type d'image .mzp non pris en charge : 0x{kind:02x}")
	step_x, step_y = tile_width - 2 * crop, tile_height - 2 * crop
	pixels = np.array(image.convert("RGBA"))
	if pixels.shape[:2] != (height - rows * 2 * crop, width - columns * 2 * crop):
		raise ValueError(f"dimensions attendues : {width - columns * 2 * crop}x{height - rows * 2 * crop}")
	# Image entourée de transparent, pour découper les débordements des tuiles
	padded = np.zeros((rows * step_y + 2 * crop + tile_height, columns * step_x + 2 * crop + tile_width, 4), np.uint8)
	padded[crop:crop + pixels.shape[0], crop:crop + pixels.shape[1]] = pixels

	for index in range(rows * columns):
		y, x = divmod(index, columns)
		wanted = padded[y * step_y:y * step_y + tile_height, x * step_x:x * step_x + tile_width]
		tile = _mzx_decompress(entries[index + 1])
		current = _hep_decode(tile, tile_width, tile_height)
		visible = (wanted[:, :, 3] > 0) | (current[:, :, 3] > 0)
		if not np.array_equal(wanted[visible], current[visible]):
			entries[index + 1] = _mzx_compress(_hep_encode(tile, wanted))
	return _write_entries(entries)
