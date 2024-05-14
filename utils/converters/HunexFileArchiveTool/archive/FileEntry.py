# Original code from
# https://github.com/LinkOFF7/HunexFileArchiveTool
# Conversion to Python by requinDr

from io import BufferedReader
from typing import List

class FileEntry:
	# def __init__(self, filename: str = '', offset: int = 0, size: int = 0):
	# 	self.filename: str = filename
	# 	self.offset: int = offset
	# 	self.size: int = size
	# 	self.reversed: List[int] = [0] * 6

	def __init__(self, reader: BufferedReader = None):
		if reader is None:
			self.filename: str = ''
			self.offset: int = 0
			self.size: int = 0
			self.reversed: List[int] = [0] * 6
			return

		self.filename = reader.read(0x60).rstrip(b'\0').decode('utf-8')
		self.offset = int.from_bytes(reader.read(4), byteorder='little')
		self.size = int.from_bytes(reader.read(4), byteorder='little')
		self.reversed = [int.from_bytes(reader.read(4), byteorder='little') for _ in range(6)]

	def write(self, writer: BufferedReader):
		filename_bytes = self.filename.encode('utf-8')
		namebuf = filename_bytes.ljust(0x60, b'\0')
		writer.write(namebuf)
		writer.write(self.offset.to_bytes(4, byteorder='little'))
		writer.write(self.size.to_bytes(4, byteorder='little'))
		for value in self.reversed:
			writer.write(value.to_bytes(4, byteorder='little'))