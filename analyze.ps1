function Analyze-Project {
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

        Write-Output "`n$Title"
        Invoke-RestMethod -Uri $Uri -Headers (Get-SonarCloudHeaders) | ConvertTo-Json -Depth 10
    }



    Write-Output 'tree.exe -I ".venv|output|__pycache__|.git|.github|.vscode|.devcontainer"'
    tree.exe -I ".venv|output|__pycache__|.git|.github|.vscode|.devcontainer"

    Write-Output "mypy --strict src/"
    & $python -m mypy --strict src/

    Write-Output "pyinstrument src/main.py --nopause"
    & $python -m pyinstrument src/main.py --nopause

    if ($env:SONAR_TOKEN) {
        $projectKey = "handsome-Druid_AICheck"
        Show-SonarCloudApiResult -Title "SonarCloud project status" -Uri "https://sonarcloud.io/api/qualitygates/project_status?projectKey=$projectKey"
        Show-SonarCloudApiResult -Title "SonarCloud measures" -Uri "https://sonarcloud.io/api/measures/component?component=$projectKey&metricKeys=bugs,vulnerabilities,code_smells,coverage,ncloc,security_hotspots"
        Show-SonarCloudApiResult -Title "SonarCloud issues" -Uri "https://sonarcloud.io/api/issues/search?componentKeys=$projectKey&resolved=false&ps=100"
    }


    if (Get-Command "scc" -ErrorAction SilentlyContinue) {
        Write-Output "scc"
        & scc
    }
}

& Analyze-Project | tee .\analyze.txt
