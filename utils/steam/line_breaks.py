"""Apostrophe retirée des caractères qui ne peuvent pas commencer une ligne.

Le moteur garde dans deux tables de .rdata les caractères interdits en début de ligne
(ponctuation, petits kana…). L'apostrophe ' y figure : dans un mot comme « l'atteindre »,
le moteur ne compte alors pour décider de couper la ligne qu'une partie du mot, qui
déborde à droite de l'écran. En français, l'apostrophe est toujours à l'intérieur d'un
mot (que version.dll garde entier), elle n'a pas besoin de cette règle.

version.dll applique ces remplacements à .rdata (fichier rdata_fr.bin de l'archive) :
chaque table est réécrite sans l'apostrophe, complétée d'un caractère nul.
"""
import struct

APOSTROPHE = "'"
# Tables du jeu (version Steam 1.1), sans leur caractère nul final
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
