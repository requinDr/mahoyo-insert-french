# Original code from
# https://github.com/LinkOFF7/HunexFileArchiveTool
# Conversion to Python by requinDr

from io import BufferedReader, BufferedWriter

class Header:
	HEADER_SIZE: int = 0x10
	ENTRY_SIZE: int = 0x80
	MAGIC: str = "HUNEXGGEFA10"

	def __init__(self, num_of_files: int):
		self.file_count: int = num_of_files

	@property
	def data_start_offset(self) -> int:
		return self.file_count * self.ENTRY_SIZE + self.HEADER_SIZE

	def write(self, writer: BufferedReader):
		writer.seek(0)
		writer.write(self.MAGIC.encode('ascii'))
		writer.write(self.file_count.to_bytes(4, byteorder='little'))

	def __init__(self, reader: BufferedReader | int):
		if isinstance(reader, int):
			self.file_count = reader
			return
		
		reader.seek(0)
		magic = reader.read(12).decode('ascii')
		if magic != self.MAGIC:
			raise Exception("Unknown file.")
		self.file_count = int.from_bytes(reader.read(4), byteorder='little')

	def get_version(self) -> int:
		return int(self.MAGIC[10])