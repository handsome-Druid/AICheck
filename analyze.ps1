function Invoke-ProjectAnalysis {
    function python {
        & ".\.venv\Scripts\python.exe" @args
    }

    [Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    $OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    chcp 65001 | Out-Null
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"

    if (Test-Path ".\sonar-token.txt") {
        $env:SONAR_TOKEN = (Get-Content ".\sonar-token.txt" -Raw).Trim()
    }

    function Write-SectionTitle {
        param(
            [string]$Title
        )

        Write-Output ""
        Write-Output "===== $Title ====="
    }

    Write-SectionTitle "uv sync"
    uv sync 2>&1

    Write-SectionTitle "pyside6-uic src/views/ui/main_window.ui -o src/views/ui/main_window_ui.py"
    & .venv\Scripts\pyside6-uic.exe ".\src\views\ui\main_window.ui" -o ".\src\views\ui\main_window_ui.py"
    & Get-Item "src\views\ui\main_window_ui.py"

    function Get-SonarCloudHeaders {
        $pair = "$($env:SONAR_TOKEN):"
        $encoded = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($pair))
        return @{ Authorization = "Basic $encoded" }
    }

    function Show-SonarCloudApiResult {
        param(
            [string]$Title,
            [string]$Uri
        )

        Invoke-RestMethod -Uri $Uri -Headers (Get-SonarCloudHeaders) | ConvertTo-Json -Depth 10
    }

    if (Get-Command "git" -ErrorAction SilentlyContinue) {
        Write-SectionTitle "git ls-files"
        & git ls-files
    }

    Write-SectionTitle "mypy --strict ./"
    & python -m mypy --strict ./

    Write-SectionTitle "pyright ./"
    & python -m pyright --pythonpath .\.venv\Scripts\python.exe ./

    Write-SectionTitle "sourcery review ./"
    & .venv\Scripts\sourcery.exe review ./ 2>&1

    $env:QT_QPA_PLATFORM = "offscreen"
    Write-SectionTitle "coverage run --source=src -m unittest discover -s tests -p ""test_*.py"""
    & python -m coverage run --source=src -m unittest discover -s tests -p "test_*.py" 2>&1
    Remove-Item env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue

    Write-SectionTitle "coverage report -m --fail-under=100"
    & python -m coverage report -m --fail-under=100

    Write-SectionTitle "pyinstrument src/main.py --nogui --nopause"
    & python -m pyinstrument src/main.py --nogui --nopause 2>&1

    if ($env:SONAR_TOKEN) {
        $projectKey = "handsome-Druid_AICheck"
        Write-SectionTitle "SonarCloud project status"
        Show-SonarCloudApiResult -Title "SonarCloud project status" -Uri "https://sonarcloud.io/api/qualitygates/project_status?projectKey=$projectKey"
        Write-SectionTitle "SonarCloud measures"
        Show-SonarCloudApiResult -Title "SonarCloud measures" -Uri "https://sonarcloud.io/api/measures/component?component=$projectKey&metricKeys=bugs,vulnerabilities,code_smells,coverage,ncloc,security_hotspots"
        Write-SectionTitle "SonarCloud issues"
        Show-SonarCloudApiResult -Title "SonarCloud issues" -Uri "https://sonarcloud.io/api/issues/search?componentKeys=$projectKey&resolved=false&ps=100"
    }


    if (Get-Command "scc" -ErrorAction SilentlyContinue) {
        Write-SectionTitle "scc"
        & scc
    }
}

if (Get-Command "uv" -ErrorAction SilentlyContinue) {
    $analysisOutput = Join-Path $env:TEMP "AICheck-analyze.txt"
    try {
        & Invoke-ProjectAnalysis | Tee-Object $analysisOutput
        Copy-Item $analysisOutput .\analyze.txt -Force
    } catch {
        & Invoke-ProjectAnalysis
    }
} else {
    Write-Output "uv is not installed. Please install uv to run the project analysis."
}
