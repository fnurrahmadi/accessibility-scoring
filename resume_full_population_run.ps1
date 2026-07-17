$workspace = $PSScriptRoot
$running = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object {
    $_.CommandLine -match 'accessibility_poc\.py.*--input properties\.csv.*--sample-size 3709'
}

if ($running) {
    Write-Host 'The full-population scoring process is already running.' -ForegroundColor Yellow
    exit 0
}

$python = 'C:\Users\Admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$log = Join-Path $workspace "data\full_population_resume_$stamp.log"
$errorLog = Join-Path $workspace "data\full_population_resume_$stamp.err"
Start-Process -FilePath $python -ArgumentList 'accessibility_poc.py --input properties.csv --sample-size 3709 --workers 1' -WorkingDirectory $workspace -WindowStyle Hidden -RedirectStandardOutput $log -RedirectStandardError $errorLog
Write-Host 'Full-population scoring resumed.' -ForegroundColor Green
Write-Host "Log: $log"
