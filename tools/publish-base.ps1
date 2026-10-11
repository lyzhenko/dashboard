#Requires -Version 7
<#
.SYNOPSIS
    Создаёт веб-публикацию базы 1С для HTTP-сервиса расширения (IIS).

.DESCRIPTION
    ЗАПУСКАТЬ ОТ ИМЕНИ АДМИНИСТРАТОРА: скрипт меняет конфигурацию IIS, а на это нужны
    права, которых у обычного процесса нет (проверка в начале скрипта).

    Что делает:
      1. создаёт каталог публикации и копирует в него модуль расширения веб-сервера
         wsisapi.dll из каталога платформы;
      2. пишет default.vrd — описание виртуального ресурса: к какой базе подключаться
         и какие HTTP-сервисы публиковать;
      3. пишет web.config — обработчик ISAPI для этого каталога;
      4. создаёт в IIS отдельный пул приложений (без управляемого кода) и отдельный
         сайт на своём порту, не трогая существующие сайты;
      5. разрешает запуск wsisapi.dll в ограничениях ISAPI и CGI.

    Альтернатива без скрипта: Конфигуратор → Администрирование → Публикация на
    веб-сервере. Этот путь надёжнее, если IIS настроен нестандартно.

.EXAMPLE
    # из консоли, запущенной от имени администратора
    .\tools\publish-base.ps1
    .\tools\publish-base.ps1 -Port 8090 -AppPath '/unf' -Server 'localhost\novofon'
#>
[CmdletBinding()]
param(
    [string]$Server = 'localhost\novofon',
    [string]$Port = '8090',
    [string]$AppPath = '/unf',
    [string]$SiteName = '1C UNF Dashboard',
    [string]$AppPoolName = '1C Dashboard',
    [string]$PublicationDir = 'C:\inetpub\1cunf',
    [string]$Extension = 'Dashboard',
    [string]$HttpServiceRoot = 'dashboard',
    [string]$PlatformPath = 'C:\Program Files\1cv8\8.3.27.2214\bin'
)

$ErrorActionPreference = 'Stop'

# --- 1. Права администратора -------------------------------------------------
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host 'Нужны права администратора. Откройте PowerShell «от имени администратора» и повторите.' -ForegroundColor Red
    Write-Host 'Без них IIS не даст ни создать сайт, ни разрешить модуль 1С.' -ForegroundColor Red
    exit 1
}

$appcmd = Join-Path $env:windir 'System32\inetsrv\appcmd.exe'
if (-not (Test-Path $appcmd)) { throw "Не найден appcmd.exe: $appcmd. Установлен ли IIS?" }

$wsisapi = Join-Path $PlatformPath 'wsisapi.dll'
if (-not (Test-Path $wsisapi)) { throw "Не найден модуль веб-сервера 1С: $wsisapi" }

# --- 2. Каталог публикации ---------------------------------------------------
Write-Host "Каталог публикации: $PublicationDir" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $PublicationDir | Out-Null
Copy-Item $wsisapi (Join-Path $PublicationDir 'wsisapi.dll') -Force

# --- 3. default.vrd ----------------------------------------------------------
# ib — строка соединения с базой в формате платформы: Srvr="localhost";Ref="novofon";
$ib = 'Srvr=&quot;{0}&quot;;Ref=&quot;{1}&quot;;' -f ($Server -split '\\')[0], ($Server -split '\\')[-1]

$vrd = @"
<?xml version="1.0" encoding="UTF-8"?>
<point xmlns="http://v8.1c.ru/8.2/virtual-resource-system"
       xmlns:xs="http://www.w3.org/2001/XMLSchema"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
       base="$AppPath"
       ib="$ib"
       enableHTTPCompression="true"
       charset="UTF-8">
	<httpServices publishByDefault="false">
		<service name="D_DashboardApi" rootUrl="$HttpServiceRoot" publishByDefault="true" />
	</httpServices>
	<ws publishByDefault="false" />
</point>
"@
[IO.File]::WriteAllText((Join-Path $PublicationDir 'default.vrd'), $vrd, (New-Object Text.UTF8Encoding($true)))

# --- 4. web.config -----------------------------------------------------------
$dllPath = Join-Path $PublicationDir 'wsisapi.dll'
$webConfig = @"
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
	<system.webServer>
		<directoryBrowse enabled="false" />
		<defaultDocument>
			<files>
				<clear />
			</files>
		</defaultDocument>
		<handlers accessPolicy="Execute, Script">
			<clear />
			<add name="1C Enterprise" path="*" verb="*" modules="IsapiModule"
			     scriptProcessor="$dllPath" resourceType="Unspecified"
			     requireAccess="Execute" preCondition="bitness64" />
		</handlers>
		<security>
			<requestFiltering>
				<hiddenSegments>
					<add segment="default.vrd" />
				</hiddenSegments>
			</requestFiltering>
		</security>
	</system.webServer>
</configuration>
"@
[IO.File]::WriteAllText((Join-Path $PublicationDir 'web.config'), $webConfig, (New-Object Text.UTF8Encoding($true)))

# --- 5. Пул приложений и сайт -----------------------------------------------
$existingPool = & $appcmd list apppools /name:$AppPoolName 2>$null
if (-not $existingPool) {
    Write-Host "Создаю пул приложений «$AppPoolName» (без управляемого кода)..." -ForegroundColor Cyan
    & $appcmd add apppool /name:$AppPoolName /managedRuntimeVersion:'' | Out-Null
    & $appcmd set apppool /apppool.name:$AppPoolName /enable32BitAppOnWin64:false | Out-Null
} else {
    Write-Host "Пул приложений «$AppPoolName» уже есть." -ForegroundColor DarkGray
}

$existingSite = & $appcmd list sites /name:$SiteName 2>$null
if (-not $existingSite) {
    Write-Host "Создаю сайт «$SiteName» на порту $Port..." -ForegroundColor Cyan
    & $appcmd add site /name:$SiteName /physicalPath:$PublicationDir /bindings:"http/*:$Port`:" | Out-Null
    & $appcmd set app "$SiteName/" /applicationPool:$AppPoolName | Out-Null
} else {
    Write-Host "Сайт «$SiteName» уже есть — обновляю привязки и пул." -ForegroundColor DarkGray
    & $appcmd set site /site.name:$SiteName /[path='/'].physicalPath:$PublicationDir | Out-Null
    & $appcmd set app "$SiteName/" /applicationPool:$AppPoolName | Out-Null
}

Write-Host 'Разрешаю запуск модуля 1С в ограничениях ISAPI и CGI...' -ForegroundColor Cyan
$restriction = & $appcmd list config -section:isapiCgiRestriction 2>$null | Out-String
if ($restriction -notmatch [regex]::Escape($dllPath)) {
    & $appcmd set config -section:isapiCgiRestriction /+"[path='$dllPath',allowed='True',description='$SiteName']" | Out-Null
}

& $appcmd start site /site.name:$SiteName 2>$null | Out-Null
& $appcmd recycle apppool /apppool.name:$AppPoolName 2>$null | Out-Null

$url = "http://localhost:$Port$AppPath/hs/$HttpServiceRoot"
Write-Host ''
Write-Host 'Публикация создана.' -ForegroundColor Green
Write-Host "  Проверка доступности: $url/health"
Write-Host "  Сводка показателей:   $url/kpi"
Write-Host ''
Write-Host 'Если ответ 401 — публикация работает, нужны учётные данные пользователя 1С с ролью D_ОсновнаяРоль.' -ForegroundColor Yellow
Write-Host 'Если 500.19 — раздел handlers заблокирован на уровне сервера: разрешите его в Диспетчере IIS (Редактор конфигурации → Разблокировать раздел).' -ForegroundColor Yellow
