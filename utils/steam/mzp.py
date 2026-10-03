# .mzp images of the Steam remaster ("mrgd00" archive of HEP tiles compressed with MZX)
#
# Format:
#  - mrgd00 archive: header, table [sector, offset, sector count, size & 0xFFFF] (sectors of
#    0x800 bytes), then the entries aligned on 8 bytes;
#  - entry 0: width, height, tile size, tile counts, type, crop, (shared palette,) then one
#    byte per tile: 0 empty (not drawn by the engine), 1 with transparency, 2 opaque;
#  - next entries: one tile each, compressed with MZX. Two kinds of images:
#    - HEP (0x0C): each tile holds a header, one palette index per pixel and its own RGBA
#      palette of 256 colors (7-bit alpha); tiles overlap their neighbours by one pixel (crop);
#    - shared palette (0x01, 8 bits): the palette follows the header in entry 0 and each tile
#      holds only the indices; changed colors take the closest one of this palette.
#
# Only the tiles whose pixels change are encoded again, the others are kept as they are.
import struct

import numpy as np
from PIL import Image

MAGIC = b"mrgd00"
SECTOR = 0x800
ALIGN = 8
MZX_MAGIC = b"MZX0"
DELTA_MAGIC = b"MZPDELTA"
HEP_HEADER_SIZE = 0x20
HEP_TYPE = 0x0C
PALETTE_TYPE = 0x01
PALETTE_8BIT = (0x01, 0x11, 0x91)  # 8-bit depths; 0x11 and 0x91: palette blocks swapped
PALETTE_SIZE = 1024
EMPTY_TILE, TRANSPARENT_TILE, OPAQUE_TILE = 0, 1, 2


def _read_entries(data: bytes) -> list[bytes]:
	if data[:6] != MAGIC:
		raise ValueError("invalid .mzp file")
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
		raise ValueError("invalid MZX tile")
	size, = struct.unpack_from("<I", data, 4)
	out = bytearray()
	literals = bytearray()  # the 128-byte ring buffer holds the last literal bytes
	clear_count = 0
	i = 8
	while len(out) < size and i < len(data):
		flags = data[i]
		i += 1
		command, argument = flags & 3, flags >> 2
		if clear_count <= 0:
			clear_count = 0x1000
		if command == 0:  # repeats the last word (zero at the start of a block)
			last = b"\0\0" if clear_count == 0x1000 else out[-2:]
			out += last * (argument + 1)
		elif command == 1:  # copy from earlier output
			distance, length = 2 * (data[i] + 1), 2 * (argument + 1)
			i += 1
			start = len(out) - distance
			if distance >= length:
				out += out[start:start + length]
			else:  # the copy overlaps what it writes: repeated pattern
				out += (out[start:] * (length // distance + 1))[:length]
		elif command == 2:  # word from the ring buffer
			for offset in (argument * 2, argument * 2 + 1):
				last = offset + (len(literals) - 1 - offset) // 128 * 128
				out.append(literals[last] if offset < len(literals) else 0)
		else:  # literal words
			chunk = data[i:i + (argument + 1) * 2]
			i += len(chunk)
			out += chunk
			literals += chunk
		clear_count -= 1 if command == 2 else argument + 1
	return bytes(out[:size])


def _match_lengths(words: np.ndarray):
	"""For each position, the longest repeat (64 words at most) of what comes before at a
	distance of 1 to 256 words, and that distance. Distances tried: the small ones (patterns),
	the row above (256 words = one tile row) and the last occurrence of the same two words."""
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
		# length of the run of equal words starting at each position
		breaks = np.where(same, total, np.arange(total + 1))
		next_break = np.minimum.accumulate(breaks[::-1])[::-1][:total]
		keep(distance, np.minimum(next_break - positions, 64))

	# last occurrence of the same pair of words, less than 256 words before
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
	"""Repeats of the previous word, copies of earlier output and literal words (greedy choice)."""
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
		# the decoder repeats zero (not the previous word) at the start of each block of 0x1000 words
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
			# literals up to the next repeat or copy of at least 3 words
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
	"""Reduces the palette to 256 colors (k-means weighted by pixel count), comparing the
	colors as displayed: premultiplied by their opacity."""
	visible = colors.astype(np.float64)
	visible[:, :3] *= visible[:, 3:] / 255
	weights = counts.astype(np.float64)
	centers = visible[np.argsort(-counts, kind="stable")[:256]].copy()

	def closest(centers):
		# squared distances summed channel by channel (no colors × centers × channels array)
		distance = (visible[:, None, 0] - centers[None, :, 0]) ** 2
		for channel in (1, 2, 3):
			distance += (visible[:, None, channel] - centers[None, :, channel]) ** 2
		return np.argmin(distance, axis=1)

	for _ in range(20):
		nearest = closest(centers)
		# weighted mean of the colors of each group (an empty group keeps its center)
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
	flat[flat[:, 3] == 0] = 0  # the color of transparent pixels does not matter
	# distinct colors: each RGBA pixel seen as an integer (same order as sorting the rows)
	packed = flat.astype(np.uint32) @ np.array([1 << 24, 1 << 16, 1 << 8, 1], np.uint32)
	keys, indices, counts = np.unique(packed, return_inverse=True, return_counts=True)
	colors = ((keys[:, None] >> np.array([24, 16, 8, 0], np.uint32)) & 0xFF).astype(np.uint8)
	if len(colors) > 256:
		colors, indices = _reduce_palette(colors, counts, indices)
	palette = np.zeros((256, 4), np.uint8)
	palette[:len(colors)] = colors
	palette[:, 3] = np.where(palette[:, 3] == 255, 255, palette[:, 3] >> 1)
	return header[:HEP_HEADER_SIZE] + indices.astype(np.uint8).tobytes() + palette.tobytes()


def _shared_palette(header: bytes, depth: int) -> np.ndarray:
	"""RGBA palette of 256 colors of a shared-palette image."""
	if depth not in PALETTE_8BIT:
		raise ValueError(f"unsupported .mzp palette depth: 0x{depth:02x}")
	palette = np.frombuffer(header, np.uint8, PALETTE_SIZE, 16).reshape(256, 4).copy()
	alpha = palette[:, 3].astype(np.uint16)
	palette[:, 3] = np.where(alpha & 0x80, 255, ((alpha << 1) | (alpha >> 6)) & 0xFF)
	if depth != 0x01:  # in each block of 32 colors, 8-15 and 16-23 are swapped
		for i in range(0, 256, 32):
			palette[i + 8:i + 16], palette[i + 16:i + 24] = palette[i + 16:i + 24].copy(), palette[i + 8:i + 16].copy()
	return palette


def _tile_codec(entries: list[bytes]):
	"""Image header, and functions decompressed tile -> RGBA pixels and
	(decompressed tile, wanted pixels) -> decompressed tile."""
	header = struct.unpack_from("<7H2B", entries[0])
	_, _, tile_width, tile_height, _, _, kind, depth, _ = header
	if kind == HEP_TYPE:
		return header, (lambda tile: _hep_decode(tile, tile_width, tile_height)), _hep_encode
	if kind == PALETTE_TYPE:
		palette = _shared_palette(entries[0], depth)
		visible = palette.astype(np.float64)
		visible[:, :3] *= visible[:, 3:] / 255

		def decode(tile):
			return palette[np.frombuffer(tile, np.uint8, tile_width * tile_height)].reshape(tile_height, tile_width, 4)

		def encode(tile, wanted):
			colors, inverse = np.unique(wanted.reshape(-1, 4), axis=0, return_inverse=True)
			shown = colors.astype(np.float64)
			shown[:, :3] *= shown[:, 3:] / 255
			nearest = np.argmin(((shown[:, None, :] - visible[None, :, :]) ** 2).sum(2), axis=1)
			return nearest[inverse.ravel()].astype(np.uint8).tobytes() + tile[tile_width * tile_height:]
		return header, decode, encode
	raise ValueError(f"unsupported .mzp image type: 0x{kind:02x}")


def encode_mzp_delta(original: bytes, image: Image.Image) -> bytes:
	"""The original .mzp with the pixels of `image`, as a delta of its changed entries only:
	version.dll rebuilds the whole file from the original of the game (same layout as
	_write_entries). Format: DELTA_MAGIC, original size, result size, count of changed
	entries, then for each one [entry index u16, size u32], and the data."""
	before = _read_entries(original)
	after = _replace_tiles(original, image)
	changed = [(i, entry) for i, (old, entry) in enumerate(zip(before, after)) if old != entry]
	header = DELTA_MAGIC + struct.pack("<IIH", len(original), len(_write_entries(after)), len(changed))
	table = b"".join(struct.pack("<HI", i, len(entry)) for i, entry in changed)
	return header + table + b"".join(entry for _, entry in changed)


def _replace_tiles(original: bytes, image: Image.Image) -> list[bytes]:
	"""Entries of the original .mzp, with the tiles that change encoded again."""
	entries = _read_entries(original)
	(width, height, tile_width, tile_height, columns, rows, kind, _, crop), decode, encode = _tile_codec(entries)
	step_x, step_y = tile_width - 2 * crop, tile_height - 2 * crop
	header = bytearray(entries[0])
	flags = 16 + (PALETTE_SIZE if kind == PALETTE_TYPE else 0)  # state of each tile
	pixels = np.array(image.convert("RGBA"))
	if pixels.shape[:2] != (height - rows * 2 * crop, width - columns * 2 * crop):
		raise ValueError(f"expected size: {width - columns * 2 * crop}x{height - rows * 2 * crop}")
	# image surrounded with transparency, to cut the overlaps of the tiles
	padded = np.zeros((rows * step_y + 2 * crop + tile_height, columns * step_x + 2 * crop + tile_width, 4), np.uint8)
	padded[crop:crop + pixels.shape[0], crop:crop + pixels.shape[1]] = pixels

	for index in range(rows * columns):
		y, x = divmod(index, columns)
		wanted = padded[y * step_y:y * step_y + tile_height, x * step_x:x * step_x + tile_width].copy()
		tile = _mzx_decompress(entries[index + 1])
		current = decode(tile)
		# only the displayed part matters: neither the overlap on the neighbours nor what lies
		# outside the image (where the original may hold anything)
		shown = (slice(crop, crop + min(step_y, pixels.shape[0] - y * step_y)),
		         slice(crop, crop + min(step_x, pixels.shape[1] - x * step_x)))
		want, have = wanted[shown], current[shown]
		visible = (want[:, :, 3] > 0) | (have[:, :, 3] > 0)
		if not np.array_equal(want[visible], have[visible]):
			if crop == 0:  # outside the image, the tile keeps its original pixels
				outside = np.ones(wanted.shape[:2], bool)
				outside[shown] = False
				wanted[outside] = current[outside]
			tile = encode(tile, wanted)
			entries[index + 1] = _mzx_compress(tile)
			# a tile that was empty would not be drawn
			alpha = decode(tile)[crop:tile_height - crop, crop:tile_width - crop, 3]
			header[flags + index] = EMPTY_TILE if not alpha.any() else OPAQUE_TILE if alpha.min() == 255 else TRANSPARENT_TILE
	entries[0] = bytes(header)
	return entries


def decode_mzp(data: bytes) -> Image.Image:
	"""RGBA image of a .mzp, without the overlaps of the tiles."""
	entries = _read_entries(data)
	(width, height, tile_width, tile_height, columns, rows, _, _, crop), decode, _ = _tile_codec(entries)
	step_x, step_y = tile_width - 2 * crop, tile_height - 2 * crop
	pixels = np.zeros((height - rows * 2 * crop, width - columns * 2 * crop, 4), np.uint8)
	for index in range(rows * columns):
		y, x = divmod(index, columns)
		tile = decode(_mzx_decompress(entries[index + 1]))
		part = pixels[y * step_y:(y + 1) * step_y, x * step_x:(x + 1) * step_x]
		part[:] = tile[crop:crop + part.shape[0], crop:crop + part.shape[1]]
	return Image.fromarray(pixels)
