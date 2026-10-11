# Общие помощники для работы с 1С из командной строки.
# Подключается остальными скриптами каталога tools:  . "$PSScriptRoot\1c-common.ps1"

$Script:PlatformPath = 'C:\Program Files\1cv8\8.3.27.2214\bin'
$Script:V8 = Join-Path $Script:PlatformPath '1cv8.exe'

function Get-1CPlatform {
    <# Возвращает путь к 1cv8.exe, проверяя его наличие. #>
    param([string]$Path = $Script:V8)
    if (-not (Test-Path $Path)) {
        throw "Не найден исполняемый файл платформы 1С: $Path. Укажите путь параметром -Platform."
    }
    return $Path
}

function Invoke-1CDesigner {
    <#
    Запускает Конфигуратор и ДОЖИДАЕТСЯ его завершения.

    Важно: 1cv8.exe — GUI-приложение. Через оператор вызова (& $v8 ...) PowerShell
    его не ждёт и возвращает управление мгновенно, поэтому используется
    Start-Process -Wait. Сообщения платформы пишутся в файл журнала (/OUT),
    иначе их не увидеть: Конфигуратор выводит их в окно, а не в stdout.

    Возвращает объект: @{ ExitCode = <int>; Log = <string>; LogPath = <string> }
    #>
    param(
        [string[]]$Arguments = @(),
        [string]$LogPath
    )

    $v8 = Get-1CPlatform
    if (-not $LogPath) {
        $LogPath = Join-Path ([IO.Path]::GetTempPath()) ("1c-{0:yyyyMMdd-HHmmss}.log" -f (Get-Date))
    }
    if (Test-Path $LogPath) { Remove-Item $LogPath -Force }

    # Режим запуска DESIGNER обязателен и всегда идёт первым: без него платформа
    # отвечает «Неопределен режим запуска» и ничего не делает.
    $all = @('DESIGNER') + @($Arguments) + @('/OUT', $LogPath, '/DisableStartupDialogs', '/DisableStartupMessages')

    # Start-Process склеивает аргументы в одну командную строку и сам их не экранирует.
    # Пустой аргумент (пустой пароль после /P) обязан доехать до платформы как "" —
    # иначе он исчезнет и следующим аргументом станет /OUT. Пути с пробелами тоже
    # требуют кавычек, иначе платформа увидит два аргумента вместо одного.
    $quoted = foreach ($a in $all) {
        if ([string]::IsNullOrEmpty($a)) { '""' }
        elseif ($a -match '[\s"]') { '"' + ($a -replace '"', '\"') + '"' }
        else { $a }
    }
    $argumentLine = $quoted -join ' '

    Write-Host "→ 1cv8.exe $argumentLine" -ForegroundColor DarkGray
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $p = Start-Process -FilePath $v8 -ArgumentList $argumentLine -Wait -PassThru
    $sw.Stop()

    $log = if (Test-Path $LogPath) { Get-Content $LogPath -Raw -Encoding UTF8 } else { '' }
    Write-Host ("← код возврата {0}, {1:N0} с" -f $p.ExitCode, $sw.Elapsed.TotalSeconds) -ForegroundColor DarkGray

    return [pscustomobject]@{
        ExitCode = $p.ExitCode
        Log      = $log
        LogPath  = $LogPath
    }
}

function Convert-DumpEncoding {
    <#
    Приводит файлы выгрузки к формату, который пишет сама 1С: UTF-8 с BOM и CRLF.
    Без BOM Конфигуратор может прочитать кириллицу как ANSI, а один только LF
    заставляет его считать файл изменённым при каждой загрузке.

    Возвращает число изменённых файлов.
    #>
    param(
        [Parameter(Mandatory)][string]$Path,
        [string[]]$Extensions = @('.xml', '.bsl')
    )

    $utf8Bom = New-Object Text.UTF8Encoding($true)
    $changed = 0
    $files = Get-ChildItem -Path $Path -Recurse -File |
        Where-Object { $Extensions -contains $_.Extension.ToLower() }

    foreach ($f in $files) {
        $bytes = [IO.File]::ReadAllBytes($f.FullName)
        $hasBom = $bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF
        $text = [Text.Encoding]::UTF8.GetString($bytes)
        if ($hasBom) { $text = $text.Substring(1) }

        $normalized = ($text -replace "`r`n", "`n") -replace "`n", "`r`n"
        $needsRewrite = (-not $hasBom) -or ($normalized -ne $text)
        if ($needsRewrite) {
            [IO.File]::WriteAllText($f.FullName, $normalized, $utf8Bom)
            $changed++
        }
    }
    return $changed
}

function Connect-1CParameters {
    <# Собирает аргументы подключения к базе: /S или /F плюс /N и /P. #>
    param(
        [string]$Server,        # например localhost\novofon
        [string]$File,          # путь к файловой базе
        [string]$User = 'Администратор',
        [string]$Password = ''
    )

    if ($Server) { $args = @("/S$Server") }
    elseif ($File) { $args = @("/F$File") }
    else { throw 'Укажите -Server (серверная база) или -File (файловая база).' }

    # /N и /P передаются отдельными аргументами; пустой пароль — пустой строкой.
    return $args + @('/N', $User, '/P', $Password)
}
