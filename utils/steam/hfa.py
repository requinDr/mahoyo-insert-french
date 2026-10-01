# Format des archives Hunex (.hfa) de la version Steam
# d'après https://github.com/LinkOFF7/HunexFileArchiveTool
import struct

MAGIC = b"HUNEXGGEFA10"
NAME_SIZE = 0x60
ENTRY_SIZE = 0x80
ALIGN = 8


def read_hfa(path: str) -> dict[str, bytes]:
	with open(path, "rb") as f:
		data = f.read()
	if data[:12] != MAGIC:
		raise ValueError(f"{path} n'est pas une archive HFA")
	count, = struct.unpack_from("<I", data, 12)
	start = 16 + count * ENTRY_SIZE
	files = {}
	for i in range(count):
		name, offset, size = struct.unpack_from(f"<{NAME_SIZE}sII", data, 16 + i * ENTRY_SIZE)
		files[name.rstrip(b"\0").decode("utf-8")] = data[start + offset:start + offset + size]
	return files


def write_hfa(path: str, files: dict[str, bytes]):
	table = bytearray()
	content = bytearray()
	for name, data in files.items():
		encoded = name.encode("utf-8")
		if len(encoded) >= NAME_SIZE:
			raise ValueError(f"Nom trop long pour une archive HFA : {name}")
		table += struct.pack(f"<{NAME_SIZE}sII24x", encoded, len(content), len(data))
		content += data + b"\xff" * (-len(data) % ALIGN)
	with open(path, "wb") as f:
		f.write(MAGIC + struct.pack("<I", len(files)) + table + content)
