#Requires -Version 7
<#
.SYNOPSIS
    Синтаксический контроль модулей расширения на загруженной базе.

.DESCRIPTION
    Выполняет /CheckModules -Extension. Расширение должно быть уже загружено в базу
    (см. load-extension.ps1). Это единственная проверка, которая видит модули так,
    как их видит платформа: структурная проверка mcp_1c её не заменяет.

.EXAMPLE
    .\tools\check-extension.ps1
#>
[CmdletBinding()]
param(
    [string]$Server = 'localhost\novofon',
    [string]$User = 'Администратор',
    [string]$Password = '',
    [string]$Extension = 'Dashboard'
)

. "$PSScriptRoot\1c-common.ps1"
$ErrorActionPreference = 'Stop'

$conn = Connect-1CParameters -Server $Server -User $User -Password $Password

Write-Host "Синтаксический контроль модулей расширения «$Extension»..." -ForegroundColor Cyan
$result = Invoke-1CDesigner -Arguments ($conn + @('/CheckModules', '-Extension', $Extension))
if ($result.Log) { Write-Host $result.Log }

if ($result.ExitCode -ne 0 -or $result.Log -match 'ошибк') {
    Write-Host "Проверка не пройдена (код $($result.ExitCode)). Журнал: $($result.LogPath)" -ForegroundColor Red
    exit 1
}
Write-Host 'Синтаксических ошибок не обнаружено.' -ForegroundColor Green
