$python = ".\.venv\Scripts\python.exe"

& $python -m nuitka `
	--onefile `
	--windows-console-mode=force `
	--output-dir=output/nuitka `
    --jobs=12 `
	src/main.py