import re

def extract_switch_line_offset(line: [str]):
	offset = int(re.match(r".*Offset (\d+)\..*", line).group(1))
	if offset is not None:
		return offset
	return None