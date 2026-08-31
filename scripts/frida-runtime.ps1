param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Command)
$root = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $root 'src'
$env:CLOUDSDK_CONFIG = Join-Path (Split-Path -Parent $root) 'frida.gcloud-gate4b'
$env:GOOGLE_CLOUD_PROJECT = 'project-b241d3e1-4c3d-4801-9c6'
$env:GOOGLE_GENAI_USE_VERTEXAI = 'TRUE'
$env:GOOGLE_CLOUD_LOCATION = 'global'
$python = Join-Path $root '.venv-gate4b\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'FRIDA runtime virtual environment is unavailable.' }
& $python @Command
exit $LASTEXITCODE
