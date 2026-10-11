#Requires -Version 7
<#
.SYNOPSIS
    Останавливает стенд дашборда: бэкенд и фронтенд.

.DESCRIPTION
    Находит процессы, слушающие порты стенда, показывает, что именно будет
    остановлено, и завершает их. Публикацию 1С и службы IIS не трогает.

.EXAMPLE
    .\tools\stop-all.ps1
#>
[CmdletBinding()]
param(
    [int[]]$Ports = @(8000, 5173)
)

$ErrorActionPreference = 'Stop'

$targets = foreach ($port in $Ports) {
    Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
}

if (-not $targets) {
    Write-Host 'Стенд не запущен: процессы на портах не найдены.' -ForegroundColor DarkGray
    return
}

$processes = $targets | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object {
    Get-Process -Id $_ -ErrorAction SilentlyContinue
} | Where-Object { $_ }

Write-Host 'Будут остановлены:' -ForegroundColor Cyan
foreach ($p in $processes) {
    $path = try { $p.Path } catch { 'путь недоступен' }
    Write-Host ("  PID {0,-6} {1,-10} {2}" -f $p.Id, $p.ProcessName, $path)
}

foreach ($p in $processes) {
    # uvicorn запускается через uv и оставляет дочерний процесс python — гасим группу.
    try {
        Stop-Process -Id $p.Id -Force -ErrorAction Stop
        Write-Host ("  остановлен PID {0}" -f $p.Id) -ForegroundColor Green
    } catch {
        Write-Host ("  не удалось остановить PID {0}: {1}" -f $p.Id, $_.Exception.Message) -ForegroundColor Yellow
    }
}

Start-Sleep -Seconds 2
$left = foreach ($port in $Ports) { Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue }
if ($left) {
    Write-Host 'Часть портов всё ещё занята — проверьте процессы вручную.' -ForegroundColor Yellow
} else {
    Write-Host 'Стенд остановлен.' -ForegroundColor Green
}
