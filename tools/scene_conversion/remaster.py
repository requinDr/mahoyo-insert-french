"""Scripts of the remaster (.chs, decompressed): instructions with their evaluated arguments.

Words are u32: an argument is pushed by (0, integer) or (3, string reference = offset - 48),
32 and 33 add and subtract the two last ones, 127 marks a source line, any other word is an
opcode; (123, 0x12345678, ...) shows a text line and 298 starts a page."""
import struct

STRING_BASE = 48
ADD, SUBTRACT = 32, 33
TEXT = 123, 0x12345678


def string_at(data: bytes, ref: int) -> str | None:
	position = ref + STRING_BASE
	if 0 < position < len(data) and data[position - 1] == 0:
		end = data.find(b'\0', position)
		if end > position:
			try:
				return data[position:end].decode('utf-8')
			except UnicodeDecodeError:
				return None
	return None


def pages(data: bytes) -> list[list[tuple]]:
	"""Instructions (opcode, args, bases) of each page, bases being the left operands of the
	additions and subtractions; the text lines as ('text', [string], [])."""
	words = struct.unpack_from(f'<{len(data) // 4}I', data)
	result, stack, bases, i = [[]], [], [], 14
	while i < len(words):
		word = words[i]
		if word == 127:
			i += 3
		elif word in (0, 3) and i + 1 < len(words):
			value = words[i + 1]
			if word == 3:
				text = string_at(data, value)
				stack.append(text if text is not None else value)
			else:
				stack.append(value - (1 << 32) if value >= 0x80000000 else value)
			i += 2
		elif word in (ADD, SUBTRACT) and len(stack) >= 2 and all(isinstance(x, int) for x in stack[-2:]):
			value = stack.pop()
			bases.append(stack[-1])
			stack[-1] += value if word == ADD else -value
			i += 1
		elif (word, words[i + 1] if i + 1 < len(words) else None) == TEXT:
			result[-1].append(('text', [string_at(data, words[i + 3])], []))
			stack, bases = [], []
			i += 15
		elif word == 300:  # end of the code
			break
		else:
			result[-1].append((word, stack, bases))
			if word == 298:
				result.append([])
			stack, bases = [], []
			i += 1
	return result
