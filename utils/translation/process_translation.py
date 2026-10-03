"""French script built from the Japanese one: each Japanese line is looked up in the
Japanese .ks sources and replaced by the same line of the French sources."""
import os
import re

import utils.config_importer as conf
from utils.translation.post_process import post_process
import utils.translation.translate_csv as csv
from utils.steam.filesmap import map as files_map
from utils.line_format import format_line_to_steam, set_indentation, transform_ruby
from utils.utils import get_file_lines, leading_spaces, progress, write_file_lines

indent_script: list[str] = get_file_lines(conf.script_source_indent)
missing_lines: dict[int, str] = {}


def find_source_line(source_lines: list[str], line: str) -> int | None:
	for index, source_line in enumerate(source_lines):
		if line.strip() == source_line.strip():
			return index
	return None


def get_partial_translation(i: int, jp_lines: list[str], fr_lines: list[str], script: list[str], last_found: int):
	"""Translation of a script line that is only part of a source line (the source line is
	split on its tags), and the index of that source line."""
	line = script[i].strip()
	for offset, jp_line in enumerate(jp_lines[last_found + 1:]):
		if line in jp_line.strip():
			index = last_found + 1 + offset
			is_first_part = jp_line.strip().startswith(line)
			parts = [part.strip() for part in re.split(r'\[.*?\]', transform_ruby(fr_lines[index])) if part.strip()]
			if len(parts) > 1:
				if is_first_part:
					return parts[0], index - 1
				try:
					# the part after the previous script line
					return parts[parts.index(script[i - 1].strip()) + 1], index - 1
				except (ValueError, IndexError):
					pass
			break
	return None, None


def format_line(index: int, line: str) -> str:
	return set_indentation(format_line_to_steam(line), leading_spaces(indent_script[index]))


def line_process(script: list[str], i: int, jp_lines: list[str], fr_lines: list[str], last_found: int) -> int:
	if script[i].strip() == "":
		return last_found
	index = find_source_line(jp_lines, script[i])
	if index is not None:
		if index < len(fr_lines) and fr_lines[index]:
			script[i] = format_line(i, fr_lines[index])
		return index
	part, index = get_partial_translation(i, jp_lines, fr_lines, script, last_found)
	if part is not None:
		script[i] = format_line(i, part)
		return index
	if conf.create_csv:
		missing_lines[i + 1] = script[i]
	return last_found


def generate_updated_translation() -> list[str]:
	script = get_file_lines(conf.script_source)
	last_found = 0
	for i in range(len(script)):
		progress(i, len(script) - 1, "Reading translations\t")
		try:
			if i + 1 in files_map:  # start of a new source file
				jp_lines = get_file_lines(os.path.join(conf.jp_sources_folder, files_map[i + 1]))
				fr_lines = get_file_lines(os.path.join(conf.fr_sources_folder, files_map[i + 1]))
			last_found = line_process(script, i, jp_lines, fr_lines, last_found)
		except Exception as e:
			print(f"Error on line {i + 1}: {e}. Skipped.")

	if conf.create_csv:
		csv.create(conf.csv_output, missing_lines)
		print(f"Lines not found: {len(missing_lines)} ({len(missing_lines) / len(script) * 100:.2f}%)")

	script = post_process(script)
	write_file_lines(conf.generated_translation, script)
	return script


if __name__ == "__main__":
	generate_updated_translation()
