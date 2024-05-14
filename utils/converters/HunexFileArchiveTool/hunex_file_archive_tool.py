# Original code from
# https://github.com/LinkOFF7/HunexFileArchiveTool
# Conversion to Python by requinDr

import os
from typing import List

from utils.converters.HunexFileArchiveTool.archive.FileEntry import FileEntry
from utils.converters.HunexFileArchiveTool.archive.Header import Header
# from archive.FileEntry import FileEntry
# from archive.Header import Header

def print_usage():
	print("WITCH ON THE HOLY NIGHT HFA (Hunex) Archive Tool by LinkOFF")
	print("")
	print("Usage: <mode> <file/folder>")
	print("  --extract\tExtract all archive contents in the directory.")
	print("  --build\tBuild a new archive from given directory.")

def build(input_dir: str, hfa_file: str, showPrints = False):
	files = [os.path.join(input_dir, f) for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
	if not files:
		print(f"Directory ({input_dir}) is empty.")
		return

	with open(hfa_file, 'wb') as writer:
		hdr = Header(len(files))
		hdr.write(writer)
		entries: List[FileEntry] = [None] * hdr.file_count
		writer.seek(hdr.data_start_offset)
		for i, file_path in enumerate(files):
			if showPrints:
				print(f"Writing: {file_path}")
			data = open(file_path, 'rb').read()
			file_entry = FileEntry()
			file_entry.filename = os.path.basename(file_path)[5:]  # trim index
			file_entry.size = len(data)
			file_entry.offset = writer.tell() - hdr.data_start_offset
			entries[i] = file_entry
			writer.write(align_data(data))

		writer.seek(hdr.HEADER_SIZE)
		for entry in entries:
			entry.write(writer)

def extract(file_path: str, showPrints = False):
	try:
		if os.path.isfile(file_path) and file_path.endswith('.hfa'):
			if showPrints:
				print(f"Unpack: {os.path.basename(file_path)}")

			with open(file_path, 'rb') as reader:
				hdr = Header(reader)
				entries: List[FileEntry] = [FileEntry(reader) for _ in range(hdr.file_count)]
				out_dir = os.path.splitext(os.path.basename(file_path))[0]
				index = 0
				for entry in entries:
					reader.seek(hdr.data_start_offset + entry.offset)
					data = reader.read(entry.size)
					path = os.path.join(out_dir, f"{index:04d}_{entry.filename}")
					if showPrints:
						print(f"Extracting: {path}")
					os.makedirs(os.path.dirname(path), exist_ok=True)
					with open(path, 'wb') as out_file:
						out_file.write(data)
					index += 1
		else:
			print(f"Error: {file_path} is not a valid HFA file.")
	except Exception as e:
		print(f"Error: {e}")

def align_data(data: bytes, align: int = 0x8) -> bytes:
	padding = align - (len(data) % align)
	if padding < align:
		data += b'\xff' * padding
	return data

def main(args: List[str]):
	if len(args) == 2:
		mode, path = args
		if mode == '--extract':
			extract(path)
		elif mode == '--build':
			build(path, path + '.hfa')
		else:
			print_usage()
	else:
		print_usage()

# if __name__ == "__main__":
# 	import sys
# 	main(sys.argv[1:])

