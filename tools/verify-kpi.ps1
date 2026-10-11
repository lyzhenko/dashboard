#Requires -Version 7
<#
.SYNOPSIS
    Проверяет HTTP-сервис расширения на опубликованной базе.

.DESCRIPTION
    Вызывает все методы сервиса и печатает сводку. Используется как приёмка после
    публикации базы: tools\publish-base.ps1.

    Проверяется:
      * /health        — сервис отвечает и видит конфигурацию;
      * /organizations — список организаций не пуст;
      * /kpi           — сводка отдаётся и суммы не «пустые»;
      * /dynamics      — ровно N месяцев, без пропусков;
      * /debtors       — детализация по контрагентам;
      * обработка неверных параметров — ожидается 400 с понятным текстом.

.EXAMPLE
    .\tools\verify-kpi.ps1 -User 'Администратор' -Password ''
    .\tools\verify-kpi.ps1 -BaseUrl 'http://localhost:8090/unf/hs/dashboard' -User 'Сервис' -Password 'secret'
#>
[CmdletBinding()]
param(
    [string]$BaseUrl = 'http://localhost:8090/unf/hs/dashboard',
    [string]$User = 'Администратор',
    [string]$Password = '',
    [string]$Period = 'month'
)

$ErrorActionPreference = 'Stop'

$pair = '{0}:{1}' -f $User, $Password
$authHeader = @{ Authorization = 'Basic ' + [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($pair)) }

$script:failures = 0
$script:checks = 0

function Invoke-Api {
    param([string]$Path, [switch]$AllowFailure)
    $url = "$BaseUrl$Path"
    try {
        $r = Invoke-WebRequest -Uri $url -Headers $authHeader -UseBasicParsing -TimeoutSec 60
        return [pscustomobject]@{ Ok = $true; Status = [int]$r.StatusCode; Json = ($r.Content | ConvertFrom-Json) }
    } catch {
        $status = 0
        $body = $null
        if ($_.Exception.Response) {
            $status = [int]$_.Exception.Response.StatusCode
            try {
                $reader = New-Object IO.StreamReader($_.Exception.Response.Content.ReadAsStream())
                $body = $reader.ReadToEnd()
            } catch { }
        }
        if ($AllowFailure) {
            return [pscustomobject]@{ Ok = $false; Status = $status; Json = $body }
        }
        throw "Запрос $url не удался (HTTP $status): $($_.Exception.Message)"
    }
}

function Check {
    param([string]$Name, [bool]$Passed, [string]$Detail = '')
    $script:checks++
    if ($Passed) {
        Write-Host ("  [ок]   {0}{1}" -f $Name, $(if ($Detail) { " — $Detail" } else { '' })) -ForegroundColor Green
    } else {
        $script:failures++
        Write-Host ("  [ОШИБКА] {0}{1}" -f $Name, $(if ($Detail) { " — $Detail" } else { '' })) -ForegroundColor Red
    }
}

function Format-Money {
    param($Value)
    if ($null -eq $Value) { return '—' }
    return ('{0:N2} ₽' -f [double]$Value)
}

Write-Host "Проверка сервиса: $BaseUrl" -ForegroundColor Cyan
Write-Host ''

# --- 1. Доступность -----------------------------------------------------------
Write-Host '1. Доступность (/health)'
try {
    $health = Invoke-Api '/health'
    Check 'сервис отвечает' ($health.Status -eq 200) "HTTP $($health.Status)"
    Check 'статус ok' ($health.Json.status -eq 'ok') "status=$($health.Json.status)"
    Check 'конфигурация определена' (-not [string]::IsNullOrWhiteSpace($health.Json.configuration)) $health.Json.configuration
    Check 'версия сервиса' (-not [string]::IsNullOrWhiteSpace($health.Json.version)) $health.Json.version
} catch {
    Check 'сервис отвечает' $false $_.Exception.Message
    Write-Host ''
    Write-Host 'Дальше идти нет смысла: сервис недоступен.' -ForegroundColor Red
    Write-Host 'Если ответ 401 — публикация работает, проверьте логин и пароль пользователя 1С с ролью D_ОсновнаяРоль.' -ForegroundColor Yellow
    Write-Host 'Если соединение отклонено — база не опубликована: tools\publish-base.ps1 (от имени администратора).' -ForegroundColor Yellow
    exit 1
}
Write-Host ''

# --- 2. Организации ----------------------------------------------------------
Write-Host '2. Организации (/organizations)'
$organizations = Invoke-Api '/organizations'
$count = @($organizations.Json.items).Count
Check 'список получен' ($count -gt 0) "организаций: $count"
$organization = $null
if ($count -gt 0) {
    $organizations.Json.items | Select-Object -First 5 | ForEach-Object {
        Write-Host ("       {0} (ИНН {1}, по умолчанию: {2})" -f $_.name, $_.inn, $_.isDefault)
    }
    $organization = $organizations.Json.items[0].id
}
Write-Host ''

# --- 3. Сводка ---------------------------------------------------------------
Write-Host "3. Сводка показателей (/kpi, период $Period)"
$query = "/kpi?period=$Period"
if ($organization) { $query += "&organization=$organization" }
$kpi = Invoke-Api $query

$m = $kpi.Json.money
$s = $kpi.Json.sales
$r = $kpi.Json.receivables
$p = $kpi.Json.payables
$st = $kpi.Json.stock
$o = $kpi.Json.orders

Write-Host ("       период: {0} .. {1} (сравнение {2} .. {3})" -f `
        $kpi.Json.period.from, $kpi.Json.period.to, $kpi.Json.period.prevFrom, $kpi.Json.period.prevTo)
Write-Host ("       деньги:      всего {0} (счета {1}, касса {2})" -f (Format-Money $m.total), (Format-Money $m.accounts), (Format-Money $m.cash))
Write-Host ("       продажи:     выручка {0}, прибыль {1}, рентабельность {2} %" -f (Format-Money $s.revenue), (Format-Money $s.grossProfit), $s.marginPct)
Write-Host ("       дебиторка:   всего {0}, просрочено {1} ({2} %)" -f (Format-Money $r.total), (Format-Money $r.overdue), $r.overduePct)
Write-Host ("       кредиторка:  всего {0}, просрочено {1} ({2} %)" -f (Format-Money $p.total), (Format-Money $p.overdue), $p.overduePct)
Write-Host ("       запасы:      {0}, номенклатур {1}, отрицательных {2}" -f (Format-Money $st.total), $st.skuCount, $st.negativeCount)
Write-Host ("       заказы:      портфель {0}, заказов {1}, просрочено к отгрузке {2}" -f (Format-Money $o.portfolio), $o.count, $o.overdueCount)
Write-Host ''

Check 'сумма денег не пустая' ($m.total -ne $null)
Check 'сумма денег равна счетам и кассе' ([math]::Abs([double]$m.total - ([double]$m.accounts + [double]$m.cash)) -lt 0.01) `
    ("{0} = {1} + {2}" -f $m.total, $m.accounts, $m.cash)
Check 'корзин задолженности пять' (@($r.buckets).Count -eq 5) "корзин: $(@($r.buckets).Count)"
Check 'сумма корзин равна итогу дебиторки' `
    ([math]::Abs(([double](($r.buckets | Measure-Object -Property amount -Sum).Sum)) - [double]$r.total) -lt 0.02) `
    ("корзины {0} против итога {1}" -f (($r.buckets | Measure-Object -Property amount -Sum).Sum), $r.total)
Check 'прибыль = выручка − себестоимость (через рентабельность)' `
    ($s.revenue -eq 0 -or [math]::Abs([double]$s.marginPct - (100 * [double]$s.grossProfit / [double]$s.revenue)) -lt 0.05) `
    "marginPct=$($s.marginPct)"

if ([double]$s.revenue -eq 0 -and [double]$m.total -eq 0 -and [double]$r.total -eq 0) {
    Write-Host '  ВНИМАНИЕ: все суммы нулевые. Либо база пустая, либо выбран не тот период,' -ForegroundColor Yellow
    Write-Host '  либо у пользователя сервиса нет прав на чтение регистров (роль D_ОсновнаяРоль).' -ForegroundColor Yellow
}
Write-Host ''

# --- 4. Динамика -------------------------------------------------------------
Write-Host '4. Динамика (/dynamics)'
$dynamics = Invoke-Api '/dynamics?months=12'
$items = @($dynamics.Json.items)
Check 'получено ровно 12 месяцев' ($items.Count -eq 12) "месяцев: $($items.Count)"
Check 'месяцы идут по возрастанию' `
    (($items.Count -le 1) -or (@(0..($items.Count - 2)) | ForEach-Object { $items[$_].month -lt $items[$_ + 1].month } | Where-Object { -not $_ }).Count -eq 0)
Check 'последний месяц совпадает с текущим' `
    ($items.Count -gt 0 -and $items[-1].month -eq (Get-Date).ToString('yyyy-MM')) "последний: $($items[-1].month)"
Write-Host ''
Write-Host '       последние месяцы:'
$items | Select-Object -Last 4 | ForEach-Object {
    Write-Host ("       {0}  выручка {1}, прибыль {2}, рентабельность {3} %" -f $_.month, (Format-Money $_.revenue), (Format-Money $_.grossProfit), $_.marginPct)
}
Write-Host ''

# --- 5. Задолженность по контрагентам ---------------------------------------
Write-Host '5. Задолженность по контрагентам (/debtors)'
$debtors = Invoke-Api '/debtors?kind=receivable&limit=5'
Write-Host ("       всего {0}, просрочено {1}, контрагентов в ответе: {2}" -f (Format-Money $debtors.Json.total), (Format-Money $debtors.Json.overdue), @($debtors.Json.items).Count)
@($debtors.Json.items) | Select-Object -First 5 | ForEach-Object {
    Write-Host ("       {0}: {1} (просрочено {2}, макс. {3} дн.)" -f $_.name, (Format-Money $_.amount), (Format-Money $_.overdue), $_.maxOverdueDays)
}
Check 'ответ не длиннее запрошенного предела' (@($debtors.Json.items).Count -le 5)
Check 'вид задолженности в ответе' ($debtors.Json.kind -eq 'receivable') "kind=$($debtors.Json.kind)"
Write-Host ''

# --- 6. Обработка неверных параметров ---------------------------------------
Write-Host '6. Обработка ошибок (ожидается HTTP 400)'
$bad = Invoke-Api '/kpi?period=decade' -AllowFailure
Check 'недопустимый период отклонён' ($bad.Status -eq 400) "HTTP $($bad.Status)"
if ($bad.Status -eq 400 -and $bad.Json) {
    $code = ($bad.Json | ConvertFrom-Json).error.code
    Check 'код ошибки bad_request' ($code -eq 'bad_request') "code=$code"
}
Write-Host ''

# --- Итог --------------------------------------------------------------------
Write-Host ('Итог: проверок {0}, ошибок {1}' -f $script:checks, $script:failures) -ForegroundColor $(if ($script:failures -eq 0) { 'Green' } else { 'Red' })
if ($script:failures -gt 0) { exit 1 }
Write-Host 'Сервис работает, показатели отдаются. Дальше — сверка сумм с типовыми отчётами УНФ:' -ForegroundColor Green
Write-Host '«Анализ бизнеса», «Пульс бизнеса», «Реестр старения дебиторской задолженности».' -ForegroundColor Green
