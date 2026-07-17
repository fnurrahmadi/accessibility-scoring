$matches = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object {
    $_.CommandLine -match 'accessibility_poc\.py.*--input properties\.csv.*--sample-size 3709'
}

if (-not $matches) {
    Write-Host 'No full-population scoring process is currently running.' -ForegroundColor Yellow
    exit 0
}

foreach ($process in $matches) {
    Invoke-CimMethod -InputObject $process -MethodName Terminate | Out-Null
    Write-Host "Paused full-population scoring process $($process.ProcessId)." -ForegroundColor Yellow
}

Write-Host 'Completed requests are cached. Run resume_full_population_run.cmd later to continue.'
