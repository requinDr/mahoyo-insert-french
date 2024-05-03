import re

# modifie le format du ruby, des .ks ([ruby char="text" text="ruby") à Steam (<text|ruby>)
PATTERN_RUBY = r'\[ruby char="([^"]+)" text="([^"]+)"\]'
def transform_ruby(ligne: str):
	match = re.search(PATTERN_RUBY, ligne)
	if match:
		remplacement = f"<{match.group(1)}|{match.group(2)}>"
		return re.sub(PATTERN_RUBY, remplacement, ligne)
	return ligne


# indente comme le script original de Steam
SPACE = "\u3000"
def indente(nbStartSpaces: int, ligne: str):
	return SPACE * nbStartSpaces + ligne


# supprime les tags
PATTERN_TAGS = r'\[.*?\]'
def remove_tags(ligne: str):
  return re.sub(PATTERN_TAGS, '', ligne)


def format_line_to_steam(ligne: str, nbStartSpaces: int = 0):
	ligne = transform_ruby(ligne)

	ligne = remove_tags(ligne)

	# supprime les espaces en fin de ligne
	ligne = ligne.rstrip() + "\n"

	ligne = indente(nbStartSpaces, ligne)

	return ligne