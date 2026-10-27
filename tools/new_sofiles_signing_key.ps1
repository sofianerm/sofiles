param([string]$KeyPath = (Join-Path $PSScriptRoot '..\.private\update-key.dpapi'))
$ErrorActionPreference = 'Stop'
$keyFile = [IO.Path]::GetFullPath($KeyPath)
if (Test-Path -LiteralPath $keyFile) { throw 'La clé existe déjà. Aucune rotation implicite.' }
Add-Type -AssemblyName System.Security
$rsa = New-Object Security.Cryptography.RSACryptoServiceProvider(3072)
$rsa.PersistKeyInCsp = $false
try {
    $privateBytes = [Text.Encoding]::UTF8.GetBytes($rsa.ToXmlString($true))
    $protected = [Security.Cryptography.ProtectedData]::Protect($privateBytes, $null, [Security.Cryptography.DataProtectionScope]::CurrentUser)
    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($keyFile)) | Out-Null
    [IO.File]::WriteAllBytes($keyFile, $protected)
    $productFile = Join-Path $PSScriptRoot '..\config\product.json'
    $product = Get-Content -LiteralPath $productFile -Raw | ConvertFrom-Json
    $product.update_public_key_xml = $rsa.ToXmlString($false)
    [IO.File]::WriteAllText([IO.Path]::GetFullPath($productFile), ($product | ConvertTo-Json -Depth 10), (New-Object Text.UTF8Encoding($false)))
    Write-Output 'Clé RSA 3072 créée ; clé privée protégée par DPAPI pour ce compte Windows. Sauvegarder séparément avant toute publication.'
} finally { $rsa.Dispose(); if ($privateBytes) { [Array]::Clear($privateBytes,0,$privateBytes.Length) } }
