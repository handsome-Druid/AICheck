$python = ".\.venv\Scripts\python.exe"



Write-Output 'tree.exe -I ".venv|output|__pycache__|.git|.github|.vscode|.devcontainer"'
tree.exe -I ".venv|output|__pycache__|.git|.github|.vscode|.devcontainer"

Write-Output "mypy --strict src/"
& $python -m mypy --strict src/

Write-Output "pyinstrument src/main.py --nopause"
& $python -m pyinstrument src/main.py --nopause


if (Get-Command "scc" -ErrorAction SilentlyContinue) {
    Write-Output "scc"
    & scc
}

