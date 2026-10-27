"""Scenarios of the original 2012 release (KAG .ks files, extracted from data.xp3)."""
import re

COMMAND = re.compile(r'@(\w+)(.*)')
ATTRIBUTE = re.compile(r'(\w+)=(\([^)]*\)\S*|\S+)')


def read(path: str) -> str:
	data = open(path, 'rb').read()
	if data[:2] == bytes([0xFF, 0xFE]):
		return data.decode('utf-16')
	if data[:3] == bytes([0xEF, 0xBB, 0xBF]):
		return data.decode('utf-8-sig')
	return data.decode('cp932', errors='replace')


def command(line: str) -> tuple[str, dict] | None:
	"""(name, attributes) of a command line (@name key=value...)."""
	m = COMMAND.match(line.strip())
	return (m[1], dict(ATTRIBUTE.findall(m[2]))) if m else None


def pages(text: str) -> list[list[tuple[str, dict]]]:
	"""Commands of each page (*pageN label)."""
	result = []
	for page in re.split(r'^\*page\d+\|.*$', text, flags=re.M)[1:]:
		result.append([c for c in map(command, page.splitlines()) if c])
	return result
