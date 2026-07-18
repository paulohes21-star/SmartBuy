param()
$ErrorActionPreference = "Stop"
$PatchDir = Split-Path -Parent $MyInvocation.MyCommand.Path

function Find-SmartBuyRoot([string]$Start) {
    $current = (Resolve-Path $Start).Path
    for ($i = 0; $i -lt 4; $i++) {
        if ((Test-Path (Join-Path $current "app\templates\base.html")) -or
            (Test-Path (Join-Path $current "templates\base.html"))) {
            return $current
        }
        $parent = Split-Path -Parent $current
        if ($parent -eq $current) { break }
        $current = $parent
    }
    return $null
}

$Project = Find-SmartBuyRoot $PatchDir
if (-not $Project) {
    throw "Projeto SmartBuy não localizado. Extraia esta pasta dentro da raiz do projeto."
}

if (Test-Path (Join-Path $Project "app\templates")) {
    $Templates = Join-Path $Project "app\templates"
    $Static = Join-Path $Project "app\static"
} else {
    $Templates = Join-Path $Project "templates"
    $Static = Join-Path $Project "static"
}

$BaseTarget = Join-Path $Templates "base.html"
$MasterTarget = Join-Path $Templates "master_data.html"
$CssTarget = Join-Path $Static "master_data_sprint7.css"

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Backup = Join-Path $Project "backups\sprint7_2_master_data_$Stamp"
New-Item -ItemType Directory -Force -Path $Backup | Out-Null

Copy-Item $BaseTarget (Join-Path $Backup "base.html") -Force
if (Test-Path $MasterTarget) { Copy-Item $MasterTarget (Join-Path $Backup "master_data.html") -Force }
if (Test-Path $CssTarget) { Copy-Item $CssTarget (Join-Path $Backup "master_data_sprint7.css") -Force }

Copy-Item (Join-Path $PatchDir "templates\master_data.html") $MasterTarget -Force
Copy-Item (Join-Path $PatchDir "static\master_data_sprint7.css") $CssTarget -Force

# Corrige somente o texto visível dos três links, sem substituir o base.html inteiro.
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$BaseText = [System.IO.File]::ReadAllText($BaseTarget)

$Usuarios = "Usu" + [char]0x00E1 + "rios"
$Inteligencia = "Intelig" + [char]0x00EA + "ncia de compras"
$Integracoes = "Integra" + [char]0x00E7 + [char]0x00F5 + "es ERP"

$BaseText = [regex]::Replace(
    $BaseText,
    '(<a\s+href="/users"[^>]*>).*?(</a>)',
    ('$1' + $Usuarios + '$2'),
    [System.Text.RegularExpressions.RegexOptions]::Singleline
)
$BaseText = [regex]::Replace(
    $BaseText,
    '(<a\s+href="/purchasing-intelligence"[^>]*>).*?(</a>)',
    ('$1' + $Inteligencia + '$2'),
    [System.Text.RegularExpressions.RegexOptions]::Singleline
)
$BaseText = [regex]::Replace(
    $BaseText,
    '(<a\s+href="/integration-core"[^>]*>).*?(</a>)',
    ('$1' + $Integracoes + '$2'),
    [System.Text.RegularExpressions.RegexOptions]::Singleline
)

# Garante a folha de estilo, sem alterar outras referências.
$CssHref = "/static/master_data_sprint7.css"
if ($BaseText -notmatch [regex]::Escape($CssHref)) {
    $Link = '<link rel="stylesheet" href="' + $CssHref + '">'
    $BaseText = $BaseText -replace '</head>', ("  " + $Link + "`r`n</head>")
}

[System.IO.File]::WriteAllText($BaseTarget, $BaseText, $Utf8NoBom)

Write-Host ""
Write-Host "Sprint 7.2 aplicada com sucesso." -ForegroundColor Green
Write-Host "Backup: $Backup"
Write-Host ""
Write-Host "Reinicie o SmartBuy e pressione Ctrl+F5 no navegador."
