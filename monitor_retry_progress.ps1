$lastDone = -1

function Get-ActiveRetryLog {
    Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'data') -Filter 'retry_*.log' |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1 -ExpandProperty FullName
}

while ($true) {
    $log = Get-ActiveRetryLog
    if (Test-Path -LiteralPath $log) {
        $entry = Select-String -LiteralPath $log -Pattern '\[(\d+)/(\d+)\] scored' | Select-Object -Last 1
        if ($entry -and $entry.Matches.Count -gt 0) {
            $done = [int]$entry.Matches[0].Groups[1].Value
            $total = [int]$entry.Matches[0].Groups[2].Value
            if ($done -ne $lastDone) {
                $partial = Join-Path $PSScriptRoot 'data\output\accessibility_poc_partial.csv'
                $rows = if (Test-Path -LiteralPath $partial) { Import-Csv -LiteralPath $partial } else { @() }
                $scored = @($rows | Where-Object processing_status -eq 'scored').Count
                $retryRequired = @($rows | Where-Object processing_status -eq 'retry_required').Count
                $percent = [math]::Round(100 * $done / $total, 1)
                Clear-Host
                Write-Host 'Failed-property retry monitor' -ForegroundColor Cyan
                Write-Host ('Processed: {0:N0} / {1:N0} properties ({2}%)' -f $done, $total, $percent)
                Write-Host ('Scored: {0:N0} | Still retry required: {1:N0}' -f $scored, $retryRequired) -ForegroundColor Green
                $lastDone = $done
            }
            if ($done -ge $total) {
                Write-Host 'Retry run complete.' -ForegroundColor Green
                break
            }
        }
    }
    Start-Sleep -Seconds 2
}
