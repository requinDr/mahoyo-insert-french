"""Scene 7-1b (Alice's dream, then Sōjūrō in the forest): its text and half of its voices are
in the game, but its script is an empty stub that nothing plays. Its staging, translated from
the original 2012 scenario (tools/scene_conversion), is in sources/scene-7-1b.jsonl; this
assembles it into a script, with a version of the archive launcher whose scenes all jump to it
and the images it needs that the engine does not know.

Compiled scripts (.chs, uncompressed): 56-byte header, u32 words, then the strings, referenced
by their offset minus STRING_BASE. An instruction is its arguments as expressions ((0, n) pushes
n, (3, ref) a string, 33 subtracts) followed by its opcode; 127 marks a line of the source.

Instructions file: one JSON array per line, [opcode, args...], ["text", script line, page end]
(a line of script_text, from 1) or ["page"]."""
import json
import struct

from utils.steam import lenzu
from utils.steam.hfa import find_in_archives

SCENE = "7_1b.chs"
INSTRUCTIONS = "sources/scene-7-1b.jsonl"
LAUNCHER = "archive.chs"
HIDDEN_LAUNCHER = "archive_hidden.chs"  # names expected by native/version.c
SCENE_NUMBER = 58  # of 7_1b, as in its stub
STRING_BASE = 48
SOURCE = "F:\\Witch\\Script\\100_scenario\\7_1b.hss"
MACROS = "Include\\define_macro.h"
LABEL_NOT_FOUND = "指定されたラベルは見つかりませんでした。"
NEGATIVE = -0x80000000  # "unchanged" value of some arguments
SUBTRACT = 33

# Images of the scene missing from the image table of WoH.exe (the engine cannot show them):
# served under the name of an image of the table that nothing uses, whose table entry gets their
# size. Entry: -1, (0, 0, w/3, h/3, w, h, w/6, 0) as u16, then the start of the next entry.
SUBSTITUTES = {
	"img3491": ("img1140",  # pump of the courtyard, 930x1260
	            bytes.fromhex("ffffffffffffffff000000009a01a601ce04ec04cd000000d30000000b000000"),
	            bytes.fromhex("ffffffffffffffff000000003601a601a203ec049b000000d30000000b000000")),
}


def data_patches() -> bytes:
	return b"".join(struct.pack("<I", len(before)) + before + after for _, before, after in SUBSTITUTES.values())


class _Script:
	def __init__(self):
		self.words: list = []
		self.line = 100

	def add(self, *items):
		self.words.extend(items)

	def mark(self):
		self.add(127, ("s", SOURCE), self.line)
		self.line += 1

	def instruction(self, opcode: int, *args):
		self.mark()
		for arg in args:
			if isinstance(arg, str):
				self.add(3, ("s", arg))
			elif arg == NEGATIVE or arg >= 0:
				self.add(0, arg)
			else:
				self.add(0, 0, 0, -arg, SUBTRACT)
		self.add(opcode)

	def build(self, header: bytes) -> bytes:
		strings: dict[str, int] = {}
		code_size = len(header) + 4 * len(self.words)
		pool = bytearray()
		for item in self.words:
			if isinstance(item, tuple) and item[1] not in strings:
				strings[item[1]] = code_size + len(pool)
				pool += item[1].encode("utf-8") + b"\0"
		words = [strings[item[1]] - STRING_BASE if isinstance(item, tuple) else item & 0xFFFFFFFF
		         for item in self.words]
		return header + struct.pack(f"<{len(words)}I", *words) + pool


def _game_file(game_dir: str, name: str) -> bytes:
	return find_in_archives(game_dir, name, exclude="data00999.hfa")


def _scene(game_dir: str) -> bytes:
	script = _Script()
	script.add(247, 1, 68, 25, 1, 3, ("s", "START"), 247, 1, 68, 25, 1, 3, ("s", LABEL_NOT_FOUND), 249)
	# start of the stub: macros, black screen on layer 0
	script.instruction(298, -1)
	script.instruction(233, 38, "eq", 23, 0)
	script.add(127, ("s", MACROS), 19, 0, 0, 833, 127, ("s", MACROS), 20, 0, 2, 270,
	           127, ("s", MACROS), 21, 337, 321)
	script.instruction(298, 0)
	script.instruction(576, 0, 0, 0, 0, 0, 0, -1, 0, 0, "CC", 0, 2, 255, 1000, 136, 240, "img0408", 0)

	index, page = 0, 1
	with open(INSTRUCTIONS, encoding="utf-8") as f:
		for line in f:
			item = json.loads(line)
			if item[0] == "text":
				text, end = ("s", f"${item[1] - 1:06d}"), item[2]
				script.mark()
				script.add(123, 0x12345678, index, text, 0, 2 if end else 1, 0, 1, 0, 0, 0, 0, 3, text, 320,
				           *([321] if end else []))
				index += 1
			elif item[0] == "page":
				script.instruction(298, page)
				page += 1
			else:
				script.instruction(*item)

	script.instruction(296, SCENE_NUMBER)
	script.mark()
	script.add(244, 300, 27)
	return script.build(lenzu.decompress(_game_file(game_dir, SCENE))[:56])


def _launchers(game_dir: str) -> dict[str, bytes]:
	"""The archive launcher and its version whose jumps to scenes (246, 3, name, 243) all go to the
	hidden scene, uncompressed and of the same size: version.dll serves the second one instead of
	the first when the hidden scene is asked for."""
	data = lenzu.decompress(_game_file(game_dir, LAUNCHER))
	hidden = bytearray(data)
	target = len(data) - STRING_BASE
	words = struct.unpack_from(f"<{len(data) // 4}I", data)
	for i in range(len(words) - 3):
		if words[i] == 246 and words[i + 1] == 3 and words[i + 3] == 243:
			struct.pack_into("<I", hidden, (i + 2) * 4, target)
	hidden += b"7_1B\0"
	return {LAUNCHER: data + bytes(len(hidden) - len(data)), HIDDEN_LAUNCHER: bytes(hidden)}


def files(game_dir: str) -> dict[str, bytes]:
	"""Files of the patch archive: the scene, the launchers, the substitute images."""
	result = {SCENE: _scene(game_dir), **_launchers(game_dir)}
	for image, (slot, _, _) in SUBSTITUTES.items():
		result[slot + ".mzp"] = _game_file(game_dir, image + ".mzp")
	return result
