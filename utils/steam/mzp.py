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
	literals = bytearray()  # le tampon circulaire de 128 octets contient les derniers octets littéraux
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
			distance, length = 2 * (data[i] + 1), 2 * (argument + 1)
			i += 1
			start = len(out) - distance
			if distance >= length:
				out += out[start:start + length]
			else:  # la copie recouvre ce qu'elle écrit : motif répété
				out += (out[start:] * (length // distance + 1))[:length]
		elif command == 2:  # mot du tampon circulaire
			for offset in (argument * 2, argument * 2 + 1):
				last = offset + (len(literals) - 1 - offset) // 128 * 128
				out.append(literals[last] if offset < len(literals) else 0)
		else:  # mots littéraux
			chunk = data[i:i + (argument + 1) * 2]
			i += len(chunk)
			out += chunk
			literals += chunk
		clear_count -= 1 if command == 2 else argument + 1
	return bytes(out[:size])


def _match_lengths(words: np.ndarray):
	"""Pour chaque position, la plus longue répétition (au plus 64 mots) de ce qui précède à une
	distance de 1 à 256 mots, et cette distance. Distances essayées : les petites (motifs), la
	ligne du dessus (256 mots = une ligne de tuile) et la dernière apparition des deux mêmes mots."""
	total = len(words)
	positions = np.arange(total)
	best_length = np.zeros(total, np.int64)
	best_distance = np.zeros(total, np.int64)

	def keep(distance, length):
		better = length > best_length
		best_length[better] = length[better]
		best_distance[better] = distance[better] if np.ndim(distance) else distance

	for distance in (*range(1, 9), 128, 256):
		same = np.zeros(total + 1, bool)
		same[distance:total] = words[distance:] == words[:-distance]
		# longueur de la suite de mots égaux qui commence à chaque position
		breaks = np.where(same, total, positions_end := np.arange(total + 1))
		next_break = np.minimum.accumulate(breaks[::-1])[::-1][:total]
		keep(distance, np.minimum(next_break - positions, 64))

	# dernière apparition de la même paire de mots, à moins de 256 mots
	pairs = words[:-1].astype(np.int64) << 16 | words[1:]
	order = np.argsort(pairs, kind="stable")
	previous = np.full(total, -1)
	same_pair = pairs[order[1:]] == pairs[order[:-1]]
	previous[order[1:][same_pair]] = order[:-1][same_pair]
	distance = positions - previous
	valid = (previous >= 0) & (distance <= 256)
	length = np.zeros(total, np.int64)
	alive = valid.copy()
	source = np.where(valid, previous, 0)
	for step in range(64):
		index = positions + step
		inside = index < total
		alive &= inside
		alive[alive] &= words[index[alive]] == words[source[alive] + step]
		length += alive
	keep(np.where(valid, distance, 0), np.where(valid, length, 0))
	return best_length.tolist(), best_distance.tolist()


def _mzx_compress(data: bytes) -> bytes:
	"""Répétitions du mot précédent, copies de ce qui précède et mots littéraux (choix glouton)."""
	data += b"\0" * (len(data) % 2)
	array = np.frombuffer(data, dtype="<u2")
	words = array.tolist()
	match_length, match_distance = _match_lengths(array)
	total = len(words)
	out = bytearray(MZX_MAGIC + struct.pack("<I", len(data)))
	clear_count = 0
	cursor = 0
	while cursor < total:
		if clear_count <= 0:
			clear_count = 0x1000
		# Le décodeur répète zéro (et non le mot précédent) au début de chaque bloc de 0x1000 mots
		last = 0 if clear_count == 0x1000 else (words[cursor - 1] if cursor else None)
		run = 0
		if last is not None:
			while run < 64 and cursor + run < total and words[cursor + run] == last:
				run += 1
		copy = match_length[cursor]
		if run >= 2 and run >= copy:
			out.append((run - 1) << 2)
			count = run
		elif copy >= 2:
			out.append(1 | (copy - 1) << 2)
			out.append(match_distance[cursor] - 1)
			count = copy
		else:
			# littéraux jusqu'à la prochaine répétition ou copie d'au moins 3 mots
			count = 1
			while count < 64 and cursor + count < total:
				k = cursor + count
				if match_length[k] >= 3 or (k + 1 < total and words[k - 1] == words[k] == words[k + 1]):
					break
				count += 1
			out.append(3 | (count - 1) << 2)
			out += data[2 * cursor:2 * (cursor + count)]
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


def _reduce_palette(colors: np.ndarray, counts: np.ndarray, indices: np.ndarray):
	"""Ramène la palette à 256 couleurs (k-means pondéré par le nombre de pixels), en
	comparant les couleurs telles qu'affichées : prémultipliées par l'opacité."""
	visible = colors.astype(np.float64)
	visible[:, :3] *= visible[:, 3:] / 255
	weights = counts.astype(np.float64)
	centers = visible[np.argsort(-counts, kind="stable")[:256]].copy()

	def closest(centers):
		# distances au carré accumulées canal par canal (même résultat que la somme sur les
		# 4 canaux, sans tableau couleurs × centres × canaux en mémoire)
		distance = (visible[:, None, 0] - centers[None, :, 0]) ** 2
		for channel in (1, 2, 3):
			distance += (visible[:, None, channel] - centers[None, :, channel]) ** 2
		return np.argmin(distance, axis=1)

	for _ in range(20):
		nearest = closest(centers)
		# moyenne pondérée des couleurs de chaque groupe (un groupe vide garde son centre)
		total = np.bincount(nearest, weights, minlength=256)
		sums = np.stack([np.bincount(nearest, weights * visible[:, c], minlength=256) for c in range(4)], 1)
		used = total > 0
		centers[used] = sums[used] / total[used, None]
	nearest = closest(centers)
	alpha = np.clip(np.round(centers[:, 3]), 0, 255)
	rgb = np.where(alpha[:, None] > 0, centers[:, :3] * 255 / np.maximum(alpha, 1)[:, None], 0)
	palette = np.column_stack((np.clip(np.round(rgb), 0, 255), alpha)).astype(np.uint8)
	return palette, nearest[indices]


def _hep_encode(header: bytes, pixels: np.ndarray) -> bytes:
	height, width = pixels.shape[:2]
	flat = pixels.reshape(-1, 4).copy()
	flat[flat[:, 3] == 0] = 0  # couleur des pixels transparents indifférente
	# couleurs distinctes : chaque pixel RGBA vu comme un entier (même ordre que trier les lignes)
	packed = flat.astype(np.uint32) @ np.array([1 << 24, 1 << 16, 1 << 8, 1], np.uint32)
	keys, indices, counts = np.unique(packed, return_inverse=True, return_counts=True)
	colors = ((keys[:, None] >> np.array([24, 16, 8, 0], np.uint32)) & 0xFF).astype(np.uint8)
	if len(colors) > 256:
		colors, indices = _reduce_palette(colors, counts, indices)
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
		# seule la partie affichée compte : ni le débordement sur les voisines, ni ce qui
		# dépasse de l'image (où l'original peut contenir n'importe quoi)
		shown = (slice(crop, crop + min(step_y, pixels.shape[0] - y * step_y)),
		         slice(crop, crop + min(step_x, pixels.shape[1] - x * step_x)))
		want, have = wanted[shown], current[shown]
		visible = (want[:, :, 3] > 0) | (have[:, :, 3] > 0)
		if not np.array_equal(want[visible], have[visible]):
			entries[index + 1] = _mzx_compress(_hep_encode(tile, wanted))
	return _write_entries(entries)


def decode_mzp(data: bytes) -> Image.Image:
	"""Image RGBA d'un .mzp (tuiles HEP), sans les débordements des tuiles."""
	entries = _read_entries(data)
	width, height, tile_width, tile_height, columns, rows, kind, _, crop = struct.unpack_from("<7H2B", entries[0])
	if kind != HEP_TYPE:
		raise ValueError(f"type d'image .mzp non pris en charge : 0x{kind:02x}")
	step_x, step_y = tile_width - 2 * crop, tile_height - 2 * crop
	pixels = np.zeros((height - rows * 2 * crop, width - columns * 2 * crop, 4), np.uint8)
	for index in range(rows * columns):
		y, x = divmod(index, columns)
		tile = _hep_decode(_mzx_decompress(entries[index + 1]), tile_width, tile_height)
		part = pixels[y * step_y:(y + 1) * step_y, x * step_x:(x + 1) * step_x]
		part[:] = tile[crop:crop + part.shape[0], crop:crop + part.shape[1]]
	return Image.fromarray(pixels)
