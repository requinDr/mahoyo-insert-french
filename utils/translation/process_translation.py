"""French script built from the Japanese one: each Japanese line is looked up in the
Japanese .ks sources and replaced by the same line of the French sources.

The Japanese text of the Steam release sometimes differs from the .ks sources: a line cut in
two, a particle added or removed. Such a line takes the French of the matching sentences of
its source line, or else of the closest Japanese line just after the last one found."""
import difflib
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

SEARCH_WINDOW = 20  # source lines looked at after the last one found
MIN_SIMILARITY = 0.8  # of the closest Japanese line
MIN_JAPANESE = 3  # characters, for lines that are not Japanese text (English, Latin, dashes)
JAPANESE = re.compile(r'[\u3040-\u30ff\u4e00-\u9fff]')  # kana and kanji
KS_TAG = re.compile(r'\[[^\]]*\]')
JP_SENTENCE_END = re.compile(r'(?<=[。！？!?])(?![」』）。！？!?])|(?<=[」』])(?=[^」』])')
FR_SENTENCE_END = re.compile(r'(?<=[.!?…」』])\s+')


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


def jp_text(line: str) -> str:
	return KS_TAG.sub('', line).replace('\u3000', '').strip()


def get_sentence_translation(line: str, jp_lines: list[str], fr_lines: list[str], last_found: int):
	"""French of a script line made of whole sentences of a source line (the Steam release cut
	the line in two), when the source line has as many sentences in both languages."""
	for index in range(last_found + 1, min(len(jp_lines), last_found + 1 + SEARCH_WINDOW)):
		jp = [s for s in JP_SENTENCE_END.split(jp_text(jp_lines[index])) if s]
		if line not in ''.join(jp) or line == ''.join(jp):
			continue
		if index >= len(fr_lines):
			break
		fr = [s for s in FR_SENTENCE_END.split(format_line_to_steam(fr_lines[index]).strip()) if s]
		for start in range(len(jp)):
			for end in range(start + 1, len(jp) + 1):
				if ''.join(jp[start:end]) == line and len(fr) == len(jp):
					# the rest of the source line can still be found by the next script line
					return ' '.join(fr[start:end]), index - (1 if end < len(jp) else 0)
		break
	return None, None


def get_closest_translation(line: str, jp_lines: list[str], fr_lines: list[str], last_found: int):
	"""French of the closest Japanese line just after the last one found (the Steam release
	changed a few characters)."""
	best, best_ratio = None, MIN_SIMILARITY
	for index in range(last_found + 1, min(len(jp_lines), last_found + 1 + SEARCH_WINDOW)):
		ratio = difflib.SequenceMatcher(None, line, jp_text(jp_lines[index])).ratio()
		if ratio > best_ratio:
			best, best_ratio = index, ratio
	if best is None or best >= len(fr_lines):
		return None, None
	return fr_lines[best], best


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
	line = script[i].strip()
	if len(JAPANESE.findall(line)) >= MIN_JAPANESE:
		for find in (get_sentence_translation, get_closest_translation):
			part, index = find(line, jp_lines, fr_lines, last_found)
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
