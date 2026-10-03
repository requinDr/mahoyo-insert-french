"""Compiles native/version.dll. Only needed after changing version.c.

Requires Visual Studio with the C++ tools ("Desktop development with C++").
Usage: python native/build_dll.py
"""
import subprocess
import sys
import tempfile
from pathlib import Path

NATIVE_DIR = Path(__file__).resolve().parent
VSWHERE = Path(r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe")


def compile_dll(output: Path, build: Path):
	if not VSWHERE.exists():
		raise FileNotFoundError("Visual Studio (C++ tools) is needed to compile version.dll")
	vs = subprocess.run([str(VSWHERE), "-latest", "-prerelease", "-products", "*",
		"-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"],
		capture_output=True, text=True, check=True).stdout.strip()
	if not vs:
		raise FileNotFoundError("Visual Studio C++ tools not found")
	vcvars = Path(vs) / "VC" / "Auxiliary" / "Build" / "vcvars64.bat"
	command = (f'call "{vcvars}" >nul && cl /nologo /O2 /W4 /WX /MT /LD "{NATIVE_DIR / "version.c"}" '
		f'/link /DEF:"{NATIVE_DIR / "version.def"}" user32.lib '
		f'/IMPLIB:"{build / "version.lib"}" /OUT:"{output}"')
	result = subprocess.run(command, shell=True, capture_output=True, text=True, cwd=build)
	if result.returncode != 0:
		raise RuntimeError(f"version.dll compilation failed:\n{result.stdout}{result.stderr}")


if __name__ == "__main__":
	try:
		with tempfile.TemporaryDirectory() as build:
			compile_dll(NATIVE_DIR / "version.dll", Path(build))
	except (OSError, RuntimeError) as error:
		sys.exit(str(error))
	print(f"Compiled: {NATIVE_DIR / 'version.dll'}")
