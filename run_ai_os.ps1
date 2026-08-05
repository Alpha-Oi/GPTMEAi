$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$defaultPython = "D:\GPTMEAi_venv_candidate\Scripts\python.exe"
$selectedPython = if ($env:GPTMEAI_PYTHON) { $env:GPTMEAI_PYTHON } else { $defaultPython }

if (-not (Test-Path -LiteralPath $selectedPython)) {
    Write-Error "GPTMEAi Python interpreter not found: $selectedPython"
    exit 1
}

& $selectedPython "-m" "ai_os" @args
exit $LASTEXITCODE
