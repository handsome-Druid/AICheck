function Invoke-ProjectAnalysis {
$python = ".\.venv\Scripts\python.exe"

    [Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    $OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    chcp 65001 | Out-Null
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"

    if (Test-Path ".\sonar-token.txt") {
        $env:SONAR_TOKEN = (Get-Content ".\sonar-token.txt" -Raw).Trim()
    }

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

    function Write-SectionTitle {
        param(
            [string]$Title
        )
        Start-Sleep -Seconds 1
        Write-Output ""
        Write-Output "===== $Title ====="
        Write-Output ""
    }



    Write-SectionTitle 'tree.exe -I ".venv|output|__pycache__|.git|.github|.vscode|.devcontainer"'
    tree.exe -I ".venv|output|__pycache__|.git|.github|.vscode|.devcontainer"

    Write-SectionTitle "mypy --strict ./"
    & $python -m mypy --strict ./

    Write-SectionTitle "pyright ./"
    & $python -m pyright ./

    Write-SectionTitle "coverage"
    & $python -m coverage run --source=src -m unittest discover -s tests -p "test_*.py"
    & $python -m coverage report -m --fail-under=95

    Write-SectionTitle "sourcery review ./"
    & $python -m sourcery review ./

    Write-SectionTitle "pyinstrument src/main.py --nopause"
    & $python -m pyinstrument src/main.py --nopause

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

& Invoke-ProjectAnalysis | Tee-Object .\analyze.txt
