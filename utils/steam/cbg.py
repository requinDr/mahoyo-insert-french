# Encodeur d'images CompressedBG_MT (.cbg) du remaster Steam
#
# Format : en-tête, puis l'image découpée en bandes de 60 lignes. Chaque bande :
#  1. prédiction : chaque octet est remplacé par sa différence avec la moyenne
#     des pixels du dessus et de gauche (BGR(A), modulo 256) ;
#  2. alternance de séquences [longueur, octets non nuls] et [longueur de zéros] ;
#  3. codage de Huffman (arbre construit de façon déterministe à partir des
#     fréquences, qui sont stockées dans la bande).
import struct

import numpy as np
from PIL import Image

MAGIC = b"CompressedBG_MT\0"
STRIPE_HEIGHT = 60
BPP_BY_MODE = {"RGBA": 32, "RGB": 24, "L": 8}


def _varint(value: int) -> bytes:
	out = bytearray()
	while value > 0x7F:
		out.append((value & 0x7F) | 0x80)
		value >>= 7
	out.append(value)
	return bytes(out)


def _predict(pixels: np.ndarray) -> np.ndarray:
	p = pixels.astype(np.int16)
	diff = p.copy()
	diff[1:, 1:] = p[1:, 1:] - ((p[:-1, 1:] + p[1:, :-1]) >> 1)
	diff[0, 1:] = p[0, 1:] - p[0, :-1]
	diff[1:, 0] = p[1:, 0] - p[:-1, 0]
	return (diff & 0xFF).astype(np.uint8).ravel()


def _zero_runs(data: np.ndarray) -> bytes:
	# Séquences alternées, en commençant par une séquence d'octets non nuls (éventuellement vide)
	is_zero = data == 0
	starts = np.flatnonzero(np.diff(is_zero.view(np.int8), prepend=-1))
	ends = np.append(starts[1:], len(data))
	out = bytearray()
	if is_zero[0]:
		out += _varint(0)
	for start, end in zip(starts.tolist(), ends.tolist()):
		out += _varint(end - start)
		if not is_zero[start]:
			out += data[start:end].tobytes()
	return bytes(out)


def _huffman_codes(weights: list[int]) -> tuple[np.ndarray, np.ndarray]:
	# Même construction que le décodeur du moteur : on assemble à chaque étape les
	# deux nœuds libres les plus légers, le premier rencontré l'emportant à égalité.
	weight = list(weights)
	parent = [-1] * 256
	children: list[tuple[int, int]] = [(-1, -1)] * 256
	total = sum(weights)
	while len(weight) < 511:
		first = second = -1
		for node in range(len(weight)):
			if weight[node] == 0 or parent[node] != -1:
				continue
			if first == -1 or weight[node] < weight[first]:
				first, second = node, first
			elif second == -1 or weight[node] < weight[second]:
				second = node
		new = len(weight)
		weight.append(weight[first] + (weight[second] if second != -1 else 0))
		children.append((first, second))
		parent[first] = new
		if second != -1:
			parent[second] = new
		parent.append(-1)
		if weight[new] >= total:
			break

	codes = np.zeros(256, np.uint64)
	lengths = np.zeros(256, np.int64)
	stack = [(len(weight) - 1, 0, 0)]
	while stack:
		node, code, length = stack.pop()
		if node < 256:
			codes[node], lengths[node] = code, length
			continue
		for bit, child in enumerate(children[node]):
			if child != -1:
				stack.append((child, code | (bit << length), length + 1))
	if lengths.max() >= 64:
		raise ValueError("Arbre de Huffman trop profond")
	return codes, lengths


def _huffman(data: bytes) -> bytes:
	symbols = np.frombuffer(data, np.uint8)
	weights = np.bincount(symbols, minlength=256).tolist()
	codes, lengths = _huffman_codes(weights)
	sym_lengths = lengths[symbols]
	sym_codes = codes[symbols]
	starts = np.concatenate(([0], np.cumsum(sym_lengths)[:-1]))
	bits = np.zeros(int(sym_lengths.sum()), np.uint8)
	for k in range(int(sym_lengths.max())):
		used = sym_lengths > k
		bits[starts[used] + k] = (sym_codes[used] >> np.uint64(k)) & np.uint64(1)
	table = b"".join(_varint(w) for w in weights)
	return struct.pack("<I", len(data)) + table + np.packbits(bits, bitorder="little").tobytes()


def encode_cbg(image: Image.Image) -> bytes:
	if image.mode not in BPP_BY_MODE:
		image = image.convert("RGBA" if "A" in image.getbands() or "transparency" in image.info else "RGB")
	bpp = BPP_BY_MODE[image.mode]
	pixels = np.array(image, np.uint8).reshape(image.height, image.width, -1)
	if bpp >= 24:
		pixels = pixels.copy()
		pixels[:, :, :3] = pixels[:, :, 2::-1]  # RGB -> BGR

	stripes = [_huffman(_zero_runs(_predict(pixels[y:y + STRIPE_HEIGHT])))
		for y in range(0, image.height, STRIPE_HEIGHT)]
	header_size = len(MAGIC) + 32 + 4 * len(stripes)
	offsets = np.cumsum([header_size] + [len(s) for s in stripes[:-1]]).tolist()
	header = MAGIC + struct.pack("<4I16x", image.width, image.height, STRIPE_HEIGHT, bpp)
	return header + struct.pack(f"<{len(stripes)}I", *offsets) + b"".join(stripes)
