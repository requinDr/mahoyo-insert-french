import re
from utils.steam.translate_swap import line_char_length

# real textbox width is 2820, but it makes the right margin too thin compared to the left one
# approximate left margin is around 144 while right is around 35
TEXTBOX_LEFT_MARGIN = 144
TEXTBOX_RIGHT_MARGIN = 35
SCREEN_WIDTH = 2944 # 1920(screen) / 32,6(cell) * 50 (ig cell width)

SPACE = ' '
JAPANESE_SPACE = '\u3000'
RUNES_TAGS = ["[ansz]", "[swel]", "[ingz]"]

# modifie le format du ruby, des .ks ([ruby char="text" text="ruby") à Steam (<text|ruby>)
PATTERN_RUBY = r'\[ruby char="([^"]+)" text="([^"]+)"\]'
def transform_ruby(ligne: str):
	match = re.search(PATTERN_RUBY, ligne)
	if match:
		for match in re.finditer(PATTERN_RUBY, ligne):
			ligne = ligne.replace(match.group(0), f"<{match.group(1)}|{match.group(2)}>")
	return ligne

def transform_custom_tags(ligne: str, nbStartSpaces: int):
	# <r> -> ^
	if re.search(r'<r>', ligne):
		ligne = re.sub(r'<r>', '^', ligne)
	# <ra> -> ^nbStartSpaces
	if re.search(r'<ra>', ligne):
		ligne = re.sub(r'<ra>', '^' + nbStartSpaces * SPACE, ligne)

	return ligne

def remove_new_ruby(ligne: str):
	search = re.search(r'<([^|]+)\|[^>]+>', ligne)
	if search:
		# <text|ruby> -> text
		for match in re.finditer(r'<([^|]+)\|[^>]+>', ligne):
			ligne = ligne.replace(match.group(0), match.group(1))
	return ligne

def indent(nbStartSpaces: int, ligne: str):
	# center the text using left spaces
	if nbStartSpaces == -2:
		spaceLength = line_char_length(SPACE)
		lineLength = line_char_length(remove_new_ruby(ligne))
		# nbStartSpaces = (TEXTBOX_WIDTH - lineLength) // (2 * spaceLength)
		nbStartSpaces = (SCREEN_WIDTH - max(TEXTBOX_LEFT_MARGIN, TEXTBOX_RIGHT_MARGIN) * 2 - lineLength) // (2 * spaceLength)

	return SPACE * nbStartSpaces + ligne

def fix_lines(ligne: str):
	# replace by the character used for making seemless lines
	ligne = ligne.replace('ー', '―')
	return ligne

PATTERN_KS_TAGS = r'\[.*?\]'
def remove_ks_tags(ligne: str):
	# if runes tags are present, change them to steam format [ansz] -> <ansz>
	hasRunesTags = False
	if any(tag in ligne for tag in RUNES_TAGS):
		hasRunesTags = True
		for tag in RUNES_TAGS:
			ligne = ligne.replace(tag, f'<{tag[1:-1]}>')

	# ", [r]　" -> ", "
	if re.search(r'[,\.\?\!A-z] ' + PATTERN_KS_TAGS + JAPANESE_SPACE, ligne):
		ligne = re.sub(r'([,\.\?\!A-z]) ' + PATTERN_KS_TAGS + JAPANESE_SPACE, r'\1 ', ligne)

	# replace Japanese space by normal space
	ligne = ligne.replace(JAPANESE_SPACE, SPACE)

	# "on dit qu'elle se base[r]sur une légende" -> "on dit qu'elle se base sur une légende"
	if re.search(r'\w+\[r\]\w+', ligne):
		ligne = re.sub(r'(\w+)\[r\](\w+)', r'\1 \2', ligne)
	
	# "on dit qu'elle se base [r] sur une légende" -> "on dit qu'elle se base sur une légende"
	if re.search(r'\w+ \[r\] \w+', ligne):
		ligne = re.sub(r'(\w+) \[r\] (\w+)', r'\1 \2', ligne)

	# remove all tags
	ligne = re.sub(PATTERN_KS_TAGS, '', ligne)

	# if runes tags were present, change them back to ks format <ansz> -> [ansz]
	if hasRunesTags:
		for tag in RUNES_TAGS:
			ligne = ligne.replace(f'<{tag[1:-1]}>', tag)

	return ligne


def format_line_to_steam(ligne: str, nbStartSpaces: int):
	ligne = transform_ruby(ligne)
	ligne = remove_ks_tags(ligne)
	ligne = transform_custom_tags(ligne, nbStartSpaces)
	ligne = fix_lines(ligne)
	ligne = ligne.strip()
	ligne = indent(nbStartSpaces, ligne)

	ligne = ligne + "\n"
	return ligne