import re

SPACE = ' '
JAPANESE_SPACE = '\u3000'

# modifie le format du ruby, des .ks ([ruby char="text" text="ruby") à Steam (<text|ruby>)
PATTERN_RUBY = r'\[ruby char="([^"]+)" text="([^"]+)"\]'
def transform_ruby(ligne: str):
	match = re.search(PATTERN_RUBY, ligne)
	if match:
		for match in re.finditer(PATTERN_RUBY, ligne):
			ligne = ligne.replace(match.group(0), f"<{match.group(1)}|{match.group(2)}>")
	return ligne


def indent(nbStartSpaces: int, ligne: str):
	return SPACE * nbStartSpaces + ligne


PATTERN_TAGS = r'\[.*?\]'
def remove_tags(ligne: str):
	# ", [r]　" -> ", "
	if re.search(r'[,\.\?\!A-z] ' + PATTERN_TAGS + JAPANESE_SPACE, ligne):
		ligne = re.sub(r'([,\.\?\!A-z]) ' + PATTERN_TAGS + JAPANESE_SPACE, r'\1 ', ligne)

	# replace Japanese space by normal space
	ligne = ligne.replace(JAPANESE_SPACE, SPACE)

	# "on dit qu'elle se base[r]sur une légende" -> "on dit qu'elle se base sur une légende"
	if re.search(r'\w+\[r\]\w+', ligne):
		ligne = re.sub(r'(\w+)\[r\](\w+)', r'\1 \2', ligne)
	
	# "on dit qu'elle se base [r] sur une légende" -> "on dit qu'elle se base sur une légende"
	if re.search(r'\w+ \[r\] \w+', ligne):
		ligne = re.sub(r'(\w+) \[r\] (\w+)', r'\1 \2', ligne)

	# remove all tags
	ligne = re.sub(PATTERN_TAGS, '', ligne)

	return ligne


def format_line_to_steam(ligne: str, nbStartSpaces: int = 0):
	ligne = transform_ruby(ligne)

	ligne = remove_tags(ligne)

	ligne = ligne.strip()

	ligne = indent(nbStartSpaces, ligne)

	ligne = ligne + "\n"

	return ligne