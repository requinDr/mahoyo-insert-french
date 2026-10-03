# Hunex archives (.hfa) of the Steam release,
# after https://github.com/LinkOFF7/HunexFileArchiveTool
import struct
from pathlib import Path

MAGIC = b"HUNEXGGEFA10"
NAME_SIZE = 0x60
ENTRY_SIZE = 0x80
ALIGN = 8


def read_hfa(path: str) -> dict[str, bytes]:
	with open(path, "rb") as f:
		data = f.read()
	if data[:12] != MAGIC:
		raise ValueError(f"{path} is not an HFA archive")
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
			raise ValueError(f"Name too long for an HFA archive: {name}")
		table += struct.pack(f"<{NAME_SIZE}sII24x", encoded, len(content), len(data))
		content += data + b"\xff" * (-len(data) % ALIGN)
	with open(path, "wb") as f:
		f.write(MAGIC + struct.pack("<I", len(files)) + table + content)


def find_in_archives(folder: str, name: str, exclude: str = "") -> bytes | None:
	"""Content of the resource `name` in the first data0????.hfa archive holding it, without
	loading whole archives (several GB)."""
	for path in sorted(Path(folder).glob("data0????.hfa")):
		if path.name == exclude:
			continue
		with open(path, "rb") as f:
			header = f.read(16)
			if header[:12] != MAGIC:
				continue
			count, = struct.unpack_from("<I", header, 12)
			table = f.read(count * ENTRY_SIZE)
			for i in range(count):
				entry_name, offset, size = struct.unpack_from(f"<{NAME_SIZE}sII", table, i * ENTRY_SIZE)
				if entry_name.rstrip(b"\0").decode("utf-8") == name:
					f.seek(16 + count * ENTRY_SIZE + offset)
					return f.read(size)
	return None
