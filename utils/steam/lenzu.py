"""LenZu decompression, used by the compressed scripts (.chs) of the Steam release.

Format: 32-byte magic, decompressed size (u32), checksum (u64), u32, 6 option bytes, a Huffman
table, then a bit stream (most significant bit first) of literals and back references."""
import heapq
import struct

MAGIC = b"LenZuCompressor\0" + b"1\0\0\0" + b"0\0\0\0" + bytes(8)


class _Bits:
	def __init__(self, data: bytes, position: int):
		self.data, self.bit = data, position * 8

	def read(self, count: int) -> int:
		value = 0
		for _ in range(count):
			value = value << 1 | (self.data[self.bit >> 3] >> (7 - (self.bit & 7))) & 1
			self.bit += 1
		return value


def _huffman_tree(values: list[int], weights: list[int], max_nodes: int) -> list:
	"""Nodes (value, child0, child1): leaves first, root last. Each new node joins the two
	lightest free nodes (the earliest on ties), the lightest one on bit 1."""
	nodes = [(value, None, None) for value in values]
	node_weights = list(weights)
	total = sum(weights)
	free = [(w, i) for i, w in enumerate(weights) if w > 0]
	heapq.heapify(free)
	while len(nodes) < max_nodes and free:
		light = heapq.heappop(free)
		other = heapq.heappop(free) if free else None
		nodes.append((None, other[1] if other else None, light[1]))
		weight = light[0] + (other[0] if other else 0)
		node_weights.append(weight)
		if weight >= total:
			break
		heapq.heappush(free, (weight, len(nodes) - 1))
	return nodes


def decompress(data: bytes) -> bytes:
	if not data.startswith(MAGIC):
		raise ValueError("not LenZu data")
	size, = struct.unpack_from("<I", data, len(MAGIC))
	position = len(MAGIC) + 16
	_, raw_bits, min_bits, _, low_bits, base_distance = data[position:position + 6]
	position += 6
	bit_count = max(raw_bits, min_bits)
	leaves = 1 << bit_count
	index_size = (bit_count + 7) // 8
	entries = int.from_bytes(data[position:position + index_size], "little") or leaves
	position += index_size
	if leaves * 4 < (index_size + 4) * entries:
		weights = list(struct.unpack_from(f"<{leaves}I", data, position))
		values = list(range(leaves))
		position += leaves * 4
	else:
		values, weights = [], []
		for _ in range(entries):
			values.append(int.from_bytes(data[position:position + index_size], "little"))
			weights.append(struct.unpack_from("<I", data, position + index_size)[0])
			position += index_size + 4
	nodes = _huffman_tree(values, weights, (leaves + 1) * leaves >> 1)
	root = len(nodes) - 1
	bits = _Bits(data, position)

	def symbol() -> int:
		node = nodes[root]
		while node[0] is None:
			node = nodes[node[1 + bits.read(1)]]
		return node[0]

	output = bytearray()
	while len(output) < size:
		back_reference = bits.read(1)
		length = symbol()
		if back_reference:
			length += base_distance
			distance = (symbol() << low_bits | bits.read(low_bits)) + base_distance
			for _ in range(length):
				output.append(output[-distance])
		else:
			output += bytes(bits.read(8) for _ in range(length + 1))
	return bytes(output[:size])
