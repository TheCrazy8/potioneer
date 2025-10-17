import PyInstaller.__main__
import os

# Build from the repository directory (the folder containing this script)
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)
print(f"Building from: {os.getcwd()}")

# Run the script to make Python file into an EXE file
PyInstaller.__main__.run([
	'docs/main.py',
	'--name=HungerBens',
	'--add-data=icon.ico;.',
	'--windowed',
	'--icon=icon.ico',
    '--manifest=app.manifest',
    '--version-file=file_version_info.txt',
    '--noconfirm',
    '--clean',
])



