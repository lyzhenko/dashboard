#Requires -Version 7
<#
.SYNOPSIS
    Собирает распространяемый файл расширения build\Dashboard.cfe.

.DESCRIPTION
    /DumpCfg -Extension выгружает расширение из базы в файл .cfe. Собирается то,
    что загружено в базу, поэтому перед сборкой выполните load-extension.ps1.

.EXAMPLE
    .\tools\build-extension.ps1
#>
[CmdletBinding()]
param(
    [string]$Server = 'localhost\novofon',
    [string]$User = 'Администратор',
    [string]$Password = '',
    [string]$Extension = 'Dashboard',
    [string]$Output = (Join-Path (Split-Path $PSScriptRoot -Parent) 'build\Dashboard.cfe')
)

. "$PSScriptRoot\1c-common.ps1"
$ErrorActionPreference = 'Stop'

$outDir = Split-Path $Output -Parent
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Force -Path $outDir | Out-Null }
if (Test-Path $Output) { Remove-Item $Output -Force }

$conn = Connect-1CParameters -Server $Server -User $User -Password $Password

Write-Host "Сборка расширения «$Extension» в $Output..." -ForegroundColor Cyan
$result = Invoke-1CDesigner -Arguments ($conn + @('/DumpCfg', $Output, '-Extension', $Extension))
if ($result.Log) { Write-Host $result.Log }

if ($result.ExitCode -ne 0 -or -not (Test-Path $Output)) {
    throw "Сборка не удалась (код $($result.ExitCode)). Журнал: $($result.LogPath)"
}

$size = (Get-Item $Output).Length
Write-Host ("Готово: {0} ({1:N0} байт)" -f $Output, $size) -ForegroundColor Green
