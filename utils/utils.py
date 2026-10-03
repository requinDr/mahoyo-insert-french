import sys

GREEN = '\033[92m'
ENDC = '\033[0m'
CLEAN_END = '\033[K'


def progress(count: float, total: float, label: str, color: str = GREEN):
	if count % (total // 100) == 0 or count == total:
		bar_len = 20
		filled_len = int(bar_len * count / total)
		percents = int(100 * count / total)
		bar = '=' * filled_len + '-' * (bar_len - filled_len)
		sys.stdout.write(f"{color}{label} [{bar}] {percents}%{ENDC}{CLEAN_END}\r")
		sys.stdout.flush()


def get_file_lines(path: str) -> list[str]:
	with open(path, encoding="utf-8") as f:
		return f.readlines()


def write_file_lines(path: str, lines: list[str]):
	with open(path, 'w', encoding="utf-8") as f:
		f.writelines(lines)


def leading_spaces(line: str) -> int:
	return len(line) - len(line.lstrip())
