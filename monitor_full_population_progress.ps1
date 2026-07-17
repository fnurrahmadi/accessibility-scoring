$propertiesFile = Join-Path $PSScriptRoot 'properties.csv'
$cacheDirectory = Join-Path $PSScriptRoot 'data\cache'
$lastDone = -1

function Get-ActiveLog {
    return Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'data') -Filter 'full_population*.log' |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1 -ExpandProperty FullName
}

function Get-CombinedCompletion {
    $properties = Import-Csv -LiteralPath $propertiesFile
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    $completed = 0
    foreach ($property in $properties) {
        $keyText = "$($property.PROPERTY_CODE)|$($property.LATITUDE)|$($property.LONGITUDE)|500|1000"
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($keyText)
        $hash = ([System.BitConverter]::ToString($sha256.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant().Substring(0, 20)
        if (Test-Path -LiteralPath (Join-Path $cacheDirectory "$hash.json")) {
            $completed++
        }
    }
    $sha256.Dispose()
    return @{ Completed = $completed; Total = $properties.Count }
}

while ($true) {
    $log = Get-ActiveLog
    if (Test-Path -LiteralPath $log) {
        $entry = Select-String -LiteralPath $log -Pattern '\[(\d+)/(\d+)\] scored' | Select-Object -Last 1
        if ($entry -and $entry.Matches.Count -gt 0) {
            $done = [int]$entry.Matches[0].Groups[1].Value
            $total = [int]$entry.Matches[0].Groups[2].Value
            if ($done -ne $lastDone) {
                $runPercent = [math]::Round(100 * $done / $total, 1)
                $combined = Get-CombinedCompletion
                $combinedPercent = [math]::Round(100 * $combined.Completed / $combined.Total, 1)
                Clear-Host
                Write-Host 'Full-population accessibility run' -ForegroundColor Cyan
                Write-Host ('Current run pass: {0:N0} / {1:N0} properties ({2}%)' -f $done, $total, $runPercent)
                Write-Host ('Total combined API completion: {0:N0} / {1:N0} properties ({2}%)' -f $combined.Completed, $combined.Total, $combinedPercent) -ForegroundColor Green
                $lastDone = $done
            }
            if ($done -ge $total) {
                Write-Host 'Run complete.' -ForegroundColor Green
                break
            }
        }
    }
    Start-Sleep -Seconds 2
}
