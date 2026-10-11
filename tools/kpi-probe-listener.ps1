#Requires -Version 7
<#
.SYNOPSIS
    Принимает отчёт самопроверки показателей от 1С и сохраняет его в файл.

.DESCRIPTION
    Поднимает простейший HTTP-приёмник на localhost (обычный TCP-сокет, поэтому
    права администратора и резервирование URL не нужны) и складывает тела POST
    в каталог build\probe. Нужен, чтобы проверить расчёт показателей на живой базе,
    когда веб-публикация базы недоступна.

    Порядок работы:
      1. запустить этот скрипт (в отдельном окне или как фоновое задание);
      2. в 1С включить регламентное задание «Dashboard: самопроверка показателей»
         (оно выключено по умолчанию) с любым расписанием;
      3. задание отправит отчёт на http://127.0.0.1:8123/report, скрипт сохранит его
         и напечатает сводку.

.EXAMPLE
    .\tools\kpi-probe-listener.ps1
    .\tools\kpi-probe-listener.ps1 -Port 8123 -TimeoutSec 600
#>
[CmdletBinding()]
param(
    [int]$Port = 8123,
    [int]$TimeoutSec = 300,
    [string]$OutDir = (Join-Path (Split-Path $PSScriptRoot -Parent) 'build\probe')
)

$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
$listener.Start()
Write-Host "Приёмник запущен: http://127.0.0.1:$Port/report" -ForegroundColor Cyan
Write-Host "Отчёты складываются в $OutDir" -ForegroundColor DarkGray
Write-Host "Ожидание до $((Get-Date).AddSeconds($TimeoutSec).ToString('HH:mm:ss'))..." -ForegroundColor DarkGray

$deadline = (Get-Date).AddSeconds($TimeoutSec)
$received = 0

try {
    while ((Get-Date) -lt $deadline) {
        if (-not $listener.Pending()) {
            Start-Sleep -Milliseconds 200
            continue
        }

        $client = $listener.AcceptTcpClient()
        try {
            $stream = $client.GetStream()
            $reader = [IO.StreamReader]::new($stream, [Text.Encoding]::UTF8)
            $requestLine = $reader.ReadLine()

            $headers = @{}
            while ($true) {
                $line = $reader.ReadLine()
                if ([string]::IsNullOrEmpty($line)) { break }
                $colon = $line.IndexOf(':')
                if ($colon -gt 0) {
                    $headers[$line.Substring(0, $colon).Trim()] = $line.Substring($colon + 1).Trim()
                }
            }

            $length = 0
            if ($headers.ContainsKey('Content-Length')) { $length = [int]$headers['Content-Length'] }

            $body = ''
            if ($length -gt 0) {
                $buffer = [char[]]::new($length)
                $read = 0
                while ($read -lt $length) {
                    $r = $reader.Read($buffer, $read, $length - $read)
                    if ($r -le 0) { break }
                    $read += $r
                }
                $body = -join $buffer[0..([Math]::Max($read - 1, 0))]
            }

            $received++
            $file = Join-Path $OutDir ('report-{0:yyyyMMdd-HHmmss}-{1}.json' -f (Get-Date), $received)
            [IO.File]::WriteAllText($file, $body, (New-Object Text.UTF8Encoding($false)))

            Write-Host ("[{0}] {1} — {2} байт → {3}" -f (Get-Date -Format 'HH:mm:ss'), $requestLine, $body.Length, (Split-Path $file -Leaf)) -ForegroundColor Green
            Write-Host $body

            $response = "HTTP/1.1 200 OK`r`nContent-Type: text/plain; charset=utf-8`r`nContent-Length: 2`r`nConnection: close`r`n`r`nOK"
            $bytes = [Text.Encoding]::UTF8.GetBytes($response)
            $stream.Write($bytes, 0, $bytes.Length)
            $stream.Flush()
        } finally {
            $client.Close()
        }
    }
} finally {
    $listener.Stop()
}

Write-Host ("Принято отчётов: {0}" -f $received) -ForegroundColor Cyan
if ($received -eq 0) {
    Write-Host 'Отчёт не пришёл. Проверьте, что регламентное задание включено и его расписание задано.' -ForegroundColor Yellow
}
