"""Apostrophe removed from the characters that cannot start a line.

The engine keeps the characters forbidden at the start of a line (punctuation, small
kana…) in two tables of .rdata. The apostrophe ' is one of them: in a word like
"l'atteindre", the engine then measures only part of the word to decide where to break the
line, and the word runs off the right of the screen. In French the apostrophe is always
inside a word (which version.dll keeps whole), so it does not need this rule.

version.dll applies these replacements to .rdata (rdata_fr.bin in the archive): each table
is rewritten without the apostrophe and padded with a null character.
"""
import struct

APOSTROPHE = "'"
# Tables of the game (Steam version 1.1), without their final null character
NO_LINE_START = (
	"\"',.:;?!ﾞﾟ･，．、。：；？！”’゛゜‐]})）〕］｝〉≫》」』】ヽヾゝゞ々‥━ー～♪ぁぃぅぇぉっゃゅょァィゥェォッャュョ",
	"\"',.?!ﾞﾟ，．、。？！”’゛゜]})）〕］｝〉≫》」』】ヽヾゝゞ々‥━ー～♪ぁぃぅぇぉっゃゅょァィゥェォッャュョ",
)


def data_patches() -> bytes:
	out = b""
	for table in NO_LINE_START:
		before = table.encode("utf-16-le")
		after = (table.replace(APOSTROPHE, "") + "\0").encode("utf-16-le")
		out += struct.pack("<I", len(before)) + before + after
	return out
