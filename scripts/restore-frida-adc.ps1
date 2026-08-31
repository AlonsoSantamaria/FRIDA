$root = Split-Path -Parent $PSScriptRoot
$env:CLOUDSDK_CONFIG = Join-Path (Split-Path -Parent $root) 'frida.gcloud-gate4b'
$env:GOOGLE_CLOUD_PROJECT = 'project-b241d3e1-4c3d-4801-9c6'
$env:GOOGLE_GENAI_USE_VERTEXAI = 'TRUE'
$env:GOOGLE_CLOUD_LOCATION = 'global'

Write-Host 'FRIDA isolated ADC restoration — official Google flow only.'
Write-Host 'Open the displayed URL in Chrome Yinalo/FRIDA, then paste the NEW verification code here.'
& 'C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.ps1' auth application-default login --no-launch-browser
if ($LASTEXITCODE -eq 0) {
  Write-Host 'ADC restoration completed. You may close this window.'
} else {
  Write-Host ('ADC restoration ended with exit code ' + $LASTEXITCODE + '.')
}
Read-Host 'Press Enter to close'
