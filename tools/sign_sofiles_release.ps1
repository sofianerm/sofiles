param(
    [Parameter(Mandatory=$true)][string]$Setup,
    [Parameter(Mandatory=$true)][string]$DownloadUrl,
    [Parameter(Mandatory=$true)][string]$NotesJson,
    [string]$KeyPath = (Join-Path $PSScriptRoot '..\.private\update-key.dpapi'),
    [string]$Output = (Join-Path $PSScriptRoot '..\dist\updates.xml')
)
$ErrorActionPreference = 'Stop'
$url = [Uri]$DownloadUrl
if (-not $url.IsAbsoluteUri -or $url.Scheme -ne 'https' -or $url.UserInfo -or $url.Fragment) { throw 'URL HTTPS requise.' }
$product = Get-Content -LiteralPath (Join-Path $PSScriptRoot '..\config\product.json') -Raw | ConvertFrom-Json
if ($product.version -notmatch '^\d{1,4}\.\d{1,4}\.\d{1,4}$') { throw 'Version invalide.' }
$setupFile = Get-Item -LiteralPath $Setup
if ($setupFile.Length -gt 200MB) { throw 'Paquet trop volumineux.' }
$notes = Get-Content -LiteralPath $NotesJson -Raw | ConvertFrom-Json
$xml = New-Object Xml.XmlDocument
$root = $xml.CreateElement('SofilesRelease'); $xml.AppendChild($root) | Out-Null
$attributes = @{ schema='1'; product='Sofiles'; channel='stable'; version=$product.version; url=$url.AbsoluteUri; sha256=(Get-FileHash -LiteralPath $Setup -Algorithm SHA256).Hash.ToLowerInvariant(); size=$setupFile.Length.ToString([Globalization.CultureInfo]::InvariantCulture) }
foreach ($name in $attributes.Keys) { $root.SetAttribute($name, $attributes[$name]) }
foreach ($lang in @('fr','en','de')) {
    if (-not $notes.$lang) { throw "Notes manquantes : $lang" }
    $node = $xml.CreateElement('Notes'); $node.SetAttribute('lang',$lang); $node.InnerText = $notes.$lang; $root.AppendChild($node) | Out-Null
}
$outputFile = [IO.Path]::GetFullPath($Output)
if ((Test-Path -LiteralPath $outputFile) -or (Test-Path -LiteralPath ($outputFile+'.sig'))) { throw 'Le manifeste existe déjà ; choisir un nouveau dossier de sortie.' }
$bytes = (New-Object Text.UTF8Encoding($false)).GetBytes($xml.OuterXml)
Add-Type -AssemblyName System.Security
$privateBytes = [Security.Cryptography.ProtectedData]::Unprotect([IO.File]::ReadAllBytes([IO.Path]::GetFullPath($KeyPath)), $null, [Security.Cryptography.DataProtectionScope]::CurrentUser)
$rsa = New-Object Security.Cryptography.RSACryptoServiceProvider
$rsa.PersistKeyInCsp = $false
try {
    $rsa.FromXmlString([Text.Encoding]::UTF8.GetString($privateBytes))
    if ($rsa.KeySize -lt 3072 -or $rsa.ToXmlString($false) -ne $product.update_public_key_xml) { throw 'La clé ne correspond pas à la clé publique du produit.' }
    $signature = $rsa.SignData($bytes, 'SHA256')
    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($outputFile)) | Out-Null
    [IO.File]::WriteAllBytes($outputFile,$bytes)
    [IO.File]::WriteAllText($outputFile+'.sig',[Convert]::ToBase64String($signature),(New-Object Text.UTF8Encoding($false)))
    Write-Output ('Manifeste et signature créés : '+$outputFile)
} finally { $rsa.Dispose(); [Array]::Clear($privateBytes,0,$privateBytes.Length) }
