import re

from utils.char_width import line_char_length

# The real text box is 2820 wide, but the right margin would then look too thin next to the
# left one (about 144 on the left, 35 on the right)
TEXTBOX_LEFT_MARGIN = 144
TEXTBOX_RIGHT_MARGIN = 35
SCREEN_WIDTH = 2944  # 1920 (screen) / 32.6 (cell) * 50 (cell width in game)
CENTER = -2  # indentation value that centers the line

SPACE = ' '
JAPANESE_SPACE = '　'
RUNES_TAGS = ["[ansz]", "[eywz]", "[swel]", "[ingz]"]
KS_TAG = r'\[.*?\]'
KS_RUBY = r'\[ruby char="([^"]+)" text="([^"]+)"\]'
STEAM_RUBY = r'<([^|]+)\|[^>]+>'


def transform_ruby(line: str) -> str:
	"""[ruby char="text" text="ruby"] (.ks) -> <text|ruby> (Steam)."""
	return re.sub(KS_RUBY, r'<\1|\2>', line)


def transform_custom_tags(line: str, start_spaces: int) -> str:
	"""Manual line breaks of the corrections: <r> -> ^, <ra> -> ^ and the indentation."""
	return line.replace('<r>', '^').replace('<ra>', '^' + start_spaces * SPACE)


def indent(start_spaces: int, line: str) -> str:
	if start_spaces == CENTER:
		space_length = line_char_length(SPACE)
		line_length = line_char_length(re.sub(STEAM_RUBY, r'\1', line))
		start_spaces = (SCREEN_WIDTH - max(TEXTBOX_LEFT_MARGIN, TEXTBOX_RIGHT_MARGIN) * 2 - line_length) // (2 * space_length)
	return SPACE * start_spaces + line.lstrip()


def remove_ks_tags(line: str) -> str:
	# runes tags are kept: [ansz] -> <ansz> while the other tags are removed
	runes = [tag for tag in RUNES_TAGS if tag in line]
	for tag in runes:
		line = line.replace(tag, f'<{tag[1:-1]}>')
	# ", [r]　" -> ", "
	line = re.sub(r'([,\.\?\!A-z]) ' + KS_TAG + JAPANESE_SPACE, r'\1 ', line)
	line = line.replace(JAPANESE_SPACE, SPACE)
	# "se base[r]sur" and "se base [r] sur" -> "se base sur"
	line = re.sub(r'(\w+)\[r\](\w+)', r'\1 \2', line)
	line = re.sub(r'(\w+) \[r\] (\w+)', r'\1 \2', line)
	line = re.sub(KS_TAG, '', line)
	for tag in runes:
		line = line.replace(f'<{tag[1:-1]}>', tag)
	return line


def set_indentation(line: str, start_spaces: int) -> str:
	line = transform_custom_tags(line, start_spaces).strip()
	return indent(start_spaces, line) + "\n"


def format_line_to_steam(line: str) -> str:
	return remove_ks_tags(transform_ruby(line)).strip() + "\n"
