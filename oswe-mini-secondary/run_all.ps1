#!/usr/bin/env pwsh
Write-Host "Running tests with pytest..."
pytest -q
if ($LASTEXITCODE -ne 0) { Write-Host "Tests failed" }
New-Item -ItemType Directory -Path results -ErrorAction SilentlyContinue | Out-Null
"{ 'note': 'run complete' }" | Out-File -FilePath results/results_post.json -Encoding utf8
