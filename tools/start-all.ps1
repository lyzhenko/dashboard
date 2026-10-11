#Requires -Version 7
<#
.SYNOPSIS
    Поднимает весь стенд дашборда: проверяет 1С, запускает бэкенд и фронтенд.

.DESCRIPTION
    Порядок:
      1. проверяет, отвечает ли опубликованный HTTP-сервис расширения 1С;
      2. применяет миграции и создаёт демо-пользователя (если его нет);
      3. запускает бэкенд (uvicorn) и фронтенд (Vite) отдельными процессами;
      4. печатает адреса и учётные данные для входа.

    Процессы запускаются в отдельных окнах PowerShell, поэтому закрытие этого
    скрипта их не останавливает. Остановить: .\tools\stop-all.ps1.

.EXAMPLE
    .\tools\start-all.ps1
    .\tools\start-all.ps1 -SkipInstall      # не запускать uv sync и pnpm install
#>
[CmdletBinding()]
param(
    [string]$OneCUrl = 'http://localhost:8080/novofon/hs/dashboard',
    [string]$OneCUser = 'Администратор',
    [string]$OneCPassword = '',
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [switch]$SkipInstall
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'

function Test-Url([string]$Url, [hashtable]$Headers = @{}) {
    try {
        $r = Invoke-WebRequest -Uri $Url -Headers $Headers -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        return [int]$r.StatusCode
    } catch {
        if ($_.Exception.Response) { return [int]$_.Exception.Response.StatusCode }
        return 0
    }
}

# --- 1. Публикация 1С --------------------------------------------------------
Write-Host '1. Проверяю HTTP-сервис 1С...' -ForegroundColor Cyan
$pair = '{0}:{1}' -f $OneCUser, $OneCPassword
$auth = @{ Authorization = 'Basic ' + [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($pair)) }
$code = Test-Url "$OneCUrl/health" $auth
if ($code -eq 200) {
    Write-Host "   сервис отвечает: $OneCUrl" -ForegroundColor Green
} elseif ($code -eq 401) {
    Write-Host "   публикация есть, но не приняты учётные данные (проверьте -OneCUser/-OneCPassword)" -ForegroundColor Yellow
} else {
    Write-Host "   сервис недоступен (HTTP $code). Проверьте публикацию базы и адрес -OneCUrl." -ForegroundColor Red
    Write-Host '   Публикация: Конфигуратор → Администрирование → Публикация на веб-сервере,' -ForegroundColor Yellow
    Write-Host '   либо tools\publish-base.ps1 от имени администратора.' -ForegroundColor Yellow
}

# --- 2. Бэкенд ---------------------------------------------------------------
Write-Host '2. Готовлю бэкенд...' -ForegroundColor Cyan
if (-not (Test-Path (Join-Path $backend '.env'))) {
    Copy-Item (Join-Path $root '.env.example') (Join-Path $backend '.env')
    Write-Host '   создан backend\.env из .env.example — проверьте секреты и адрес 1С' -ForegroundColor Yellow
}
Push-Location $backend
try {
    if (-not $SkipInstall) { & uv sync --quiet }
    & uv run alembic upgrade head | Out-Null
    & uv run python -m app.cli seed-demo | Out-Null
} finally { Pop-Location }
Write-Host '   миграции применены, демо-пользователь на месте' -ForegroundColor Green

# --- 3. Запуск процессов -----------------------------------------------------
Write-Host '3. Запускаю бэкенд и фронтенд...' -ForegroundColor Cyan

$backendCmd = "Set-Location '$backend'; uv run uvicorn app.main:app --port $BackendPort"
Start-Process -FilePath 'pwsh' -ArgumentList '-NoExit', '-Command', $backendCmd | Out-Null

Start-Sleep -Seconds 6

$frontendCmd = "Set-Location '$frontend'; pnpm dev --port $FrontendPort"
Start-Process -FilePath 'pwsh' -ArgumentList '-NoExit', '-Command', $frontendCmd | Out-Null

Start-Sleep -Seconds 8

# --- 4. Итог -----------------------------------------------------------------
$backendCode = Test-Url "http://localhost:$BackendPort/api/v1/health"
$frontendCode = Test-Url "http://localhost:$FrontendPort/"

Write-Host ''
Write-Host 'Стенд запущен:' -ForegroundColor Green
Write-Host ("  дашборд:  http://localhost:{0}   (HTTP {1})" -f $FrontendPort, $frontendCode)
Write-Host ("  бэкенд:   http://localhost:{0}/docs   (HTTP {1})" -f $BackendPort, $backendCode)
Write-Host ("  1С:       {0}" -f $OneCUrl)
Write-Host ''
Write-Host 'Вход в дашборд: rukovoditel / dashboard  (демо-пользователь, только для разработки)'
Write-Host 'Остановить: .\tools\stop-all.ps1'
