$ErrorActionPreference = 'Stop'

Add-Type -Path (Join-Path $PSHOME 'Microsoft.CodeAnalysis.dll')
Add-Type -Path (Join-Path $PSHOME 'Microsoft.CodeAnalysis.CSharp.dll')

$projectRoot = $PSScriptRoot
$outputDirectory = Join-Path $projectRoot 'bin\Release\net10.0-windows'
$outputPath = Join-Path $outputDirectory 'PqLabel.dll'
$autoCadDirectory = 'C:\Program Files\Autodesk\AutoCAD 2027'

$referencePaths = [System.Collections.Generic.HashSet[string]]::new(
    [System.StringComparer]::OrdinalIgnoreCase)

Get-ChildItem $PSHOME -Filter '*.dll' | ForEach-Object {
    try {
        [void][System.Reflection.AssemblyName]::GetAssemblyName($_.FullName)
        [void]$referencePaths.Add($_.FullName)
    }
    catch {
        # Ignore native DLLs.
    }
}

'acdbmgd.dll', 'acmgd.dll', 'accoremgd.dll', 'AcWindows.dll', 'AdWindows.dll' | ForEach-Object {
    [void]$referencePaths.Add((Join-Path $autoCadDirectory $_))
}

$references = [System.Collections.Generic.List[Microsoft.CodeAnalysis.MetadataReference]]::new()
$referencePaths | ForEach-Object {
    $references.Add([Microsoft.CodeAnalysis.MetadataReference]::CreateFromFile($_))
}

$parseOptions = [Microsoft.CodeAnalysis.CSharp.CSharpParseOptions]::Default.WithLanguageVersion(
    [Microsoft.CodeAnalysis.CSharp.LanguageVersion]::Latest)
$syntaxTrees = [System.Collections.Generic.List[Microsoft.CodeAnalysis.SyntaxTree]]::new()
Get-ChildItem $projectRoot -Recurse -Filter '*.cs' |
    Where-Object { $_.FullName -notmatch '[\\/](bin|obj)[\\/]' } | ForEach-Object {
    $source = [System.IO.File]::ReadAllText($_.FullName)
    $syntaxTrees.Add([Microsoft.CodeAnalysis.CSharp.CSharpSyntaxTree]::ParseText(
        $source, $parseOptions, $_.FullName))
}

$options = [Microsoft.CodeAnalysis.CSharp.CSharpCompilationOptions]::new(
    [Microsoft.CodeAnalysis.OutputKind]::DynamicallyLinkedLibrary)
$options = $options.WithOptimizationLevel([Microsoft.CodeAnalysis.OptimizationLevel]::Release)
$options = $options.WithPlatform([Microsoft.CodeAnalysis.Platform]::X64)

$compilation = [Microsoft.CodeAnalysis.CSharp.CSharpCompilation]::Create(
    'PqLabel', $syntaxTrees, $references, $options)

[System.IO.Directory]::CreateDirectory($outputDirectory) | Out-Null
$outputStream = [System.IO.File]::Create($outputPath)
try {
    $result = $compilation.Emit($outputStream)
}
finally {
    $outputStream.Dispose()
}
if (-not $result.Success) {
    $result.Diagnostics |
        Where-Object { $_.Severity -eq [Microsoft.CodeAnalysis.DiagnosticSeverity]::Error } |
        ForEach-Object { Write-Error $_.ToString() }
    exit 1
}

Write-Output $outputPath
