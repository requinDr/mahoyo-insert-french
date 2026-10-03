import csv as csv_module
import re

import utils.config_importer as conf
from utils.line_format import CENTER, format_line_to_steam, set_indentation
import utils.translation.translate_csv as csv
from utils.utils import get_file_lines, leading_spaces

corrections = None if conf.create_csv else csv.get_csv(conf.csv_input)
indent_script: list[str] = get_file_lines(conf.script_source_indent)


def load_final_replacements(path: str) -> list[tuple[str, str]]:
	def unescape(text: str) -> str:
		return re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), text)
	with open(path, encoding='utf-8', newline='') as f:
		return [(unescape(row['avant']), unescape(row['après'])) for row in csv_module.DictReader(f) if row['avant']]


def apply_correction(index: int, line: str) -> str:
	"""Line replaced by its correction, if any: new text and/or indentation (number of
	spaces, "center", or the indentation of the English script by default)."""
	row = corrections.get(index + 1) if corrections else None
	if row is None:
		return line
	translation = row[csv.TRANSLATION].strip()
	if translation:
		line = format_line_to_steam(translation)
	spaces = row[csv.START_SPACES].strip()
	if spaces == "center":
		start_spaces = CENTER
	elif spaces:
		start_spaces = int(spaces)
	else:
		start_spaces = leading_spaces(indent_script[index])
	return line if start_spaces == -1 else set_indentation(line, start_spaces)


def post_process(script: list[str]) -> list[str]:
	final_replacements = load_final_replacements(conf.replacements_csv)
	for i, line in enumerate(script):
		line = apply_correction(i, line)
		for before, after in final_replacements:
			line = line.replace(before, after)
		script[i] = line
	return script
