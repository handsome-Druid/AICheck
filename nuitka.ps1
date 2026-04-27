$python = ".\.venv\Scripts\python.exe"

& $python -m nuitka `
	--onefile `
	--windows-console-mode=disable `
	--output-dir=output/nuitka `
    --jobs=12 `
	--enable-plugin=pyside6 `
	src/main.py