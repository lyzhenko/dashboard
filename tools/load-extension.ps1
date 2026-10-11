#Requires -Version 7
<#
.SYNOPSIS
    Загружает исходники расширения из unf_ext в базу 1С и применяет изменения к базе.

.DESCRIPTION
    Порядок обязателен: сначала файлы (LoadConfigFromFiles), потом обновление
    конфигурации БД (UpdateDBCfg). Перед загрузкой файлы приводятся к формату 1С
    (UTF-8 с BOM, CRLF).

    Загрузка требует МОНОПОЛЬНОГО доступа к базе. Если открыт сеанс 1С или идёт
    регламентное задание, Конфигуратор молча ждёт — это выглядит как зависание.
    Признак: процесс 1cv8.exe почти не грузит ЦП. Закройте сеансы и повторите.

.EXAMPLE
    .\tools\load-extension.ps1
    .\tools\load-extension.ps1 -Server 'localhost\novofon' -User 'Администратор' -Password ''
#>
[CmdletBinding()]
param(
    [string]$Server = 'localhost\novofon',
    [string]$User = 'Администратор',
    [string]$Password = '',
    [string]$Extension = 'Dashboard',
    [string]$Source = (Join-Path (Split-Path $PSScriptRoot -Parent) 'unf_ext')
)

. "$PSScriptRoot\1c-common.ps1"
$ErrorActionPreference = 'Stop'

if (-not (Test-Path $Source)) { throw "Не найден каталог исходников расширения: $Source" }

Write-Host "Приведение файлов к формату 1С (UTF-8 BOM + CRLF)..." -ForegroundColor Cyan
$changed = Convert-DumpEncoding -Path $Source
Write-Host "  изменено файлов: $changed"

$conn = Connect-1CParameters -Server $Server -User $User -Password $Password

Write-Host "Загрузка исходников в расширение «$Extension»..." -ForegroundColor Cyan
$load = Invoke-1CDesigner -Arguments ($conn + @('/LoadConfigFromFiles', $Source, '-Extension', $Extension))
if ($load.Log) { Write-Host $load.Log }
if ($load.ExitCode -ne 0) { throw "LoadConfigFromFiles завершился с кодом $($load.ExitCode). Журнал: $($load.LogPath)" }

Write-Host "Обновление конфигурации базы..." -ForegroundColor Cyan
$update = Invoke-1CDesigner -Arguments ($conn + @('/UpdateDBCfg', '-Extension', $Extension))
if ($update.Log) { Write-Host $update.Log }
if ($update.ExitCode -ne 0) { throw "UpdateDBCfg завершился с кодом $($update.ExitCode). Журнал: $($update.LogPath)" }

Write-Host 'Готово: расширение загружено и применено к базе.' -ForegroundColor Green
Write-Host 'Перезапустите сеанс 1С, чтобы изменения увидел сервер.' -ForegroundColor Yellow
