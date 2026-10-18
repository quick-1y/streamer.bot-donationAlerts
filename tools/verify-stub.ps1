# Optional dev-only check: compares tools/compile-check/Stub/CphStub.cs with the
# Streamer.bot Plugin Interface of a local install, using reflection-only metadata
# loading (no code from the install is executed). With -Facts it also prints a few
# offline facts (EventType values, bundled file versions) used by the live-spike findings.
#
# Reads only: Streamer.bot.Plugin.Interface.dll, Streamer.bot.Common.dll (with -Facts),
# and the version resources of three files. It never opens the data folder or logs,
# and it prints only the signatures of the members the stub itself declares.
#
# Usage (Windows PowerShell 5.1):
#   powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/verify-stub.ps1 -StreamerBotDir <folder> [-Facts]
# Exit code: 1 when any DRIFT line was printed, otherwise 0.

param(
    [Parameter(Mandatory = $true)][string]$StreamerBotDir,
    [switch]$Facts
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:SbDir = (Resolve-Path -LiteralPath $StreamerBotDir).ProviderPath
$script:DriftCount = 0

$null = [AppDomain]::CurrentDomain.add_ReflectionOnlyAssemblyResolve({
    param($sender, $eventArgs)
    $simpleName = $eventArgs.Name.Split(',')[0]
    $candidate = Join-Path $script:SbDir ($simpleName + '.dll')
    if (Test-Path -LiteralPath $candidate)
    {
        return [Reflection.Assembly]::ReflectionOnlyLoadFrom($candidate)
    }
    return [Reflection.Assembly]::ReflectionOnlyLoad($eventArgs.Name)
})

function Write-Drift([string]$text)
{
    $script:DriftCount++
    Write-Output ('DRIFT ' + $text)
}

function Get-ExportedTypesSafe([Reflection.Assembly]$assembly)
{
    try
    {
        return $assembly.GetExportedTypes()
    }
    catch [Reflection.ReflectionTypeLoadException]
    {
        return @($_.Exception.Types | Where-Object { $null -ne $_ })
    }
}

function Split-TopLevel([string]$text)
{
    $parts = New-Object System.Collections.Generic.List[string]
    $depth = 0
    $current = New-Object System.Text.StringBuilder
    foreach ($ch in $text.ToCharArray())
    {
        if ($ch -eq '<') { $depth++ }
        elseif ($ch -eq '>') { $depth-- }
        if ($ch -eq ',' -and $depth -eq 0)
        {
            $parts.Add($current.ToString().Trim())
            $null = $current.Clear()
        }
        else
        {
            $null = $current.Append($ch)
        }
    }
    $last = $current.ToString().Trim()
    if ($last.Length -gt 0) { $parts.Add($last) }
    return , $parts.ToArray()
}

function ConvertTo-ClrName([string]$typeText)
{
    $keywords = @{
        'string' = 'String'; 'bool' = 'Boolean'; 'int' = 'Int32'; 'long' = 'Int64'
        'double' = 'Double'; 'decimal' = 'Decimal'; 'object' = 'Object'; 'void' = 'Void'
    }
    $text = $typeText.Trim()
    $suffix = ''
    if ($text.EndsWith('[]'))
    {
        $suffix = '[]'
        $text = $text.Substring(0, $text.Length - 2)
    }
    if ($text -match '^(\w+)<(.+)>$')
    {
        $count = (Split-TopLevel $Matches[2]).Count
        return $Matches[1] + [string][char]96 + $count + $suffix
    }
    if ($keywords.ContainsKey($text)) { return $keywords[$text] + $suffix }
    return $text + $suffix
}

function Read-StubInterface([string]$stubPath)
{
    $members = New-Object System.Collections.Generic.List[object]
    $inside = $false
    foreach ($line in (Get-Content -LiteralPath $stubPath -Encoding UTF8))
    {
        if ($line -match '^\s*public\s+interface\s+IInlineInvokeProxy\b') { $inside = $true; continue }
        if (-not $inside) { continue }
        if ($line -match '^\}') { break }
        if ($line -match '^\s+(\S+)\s+(\w+)(?:<\w+>)?\((.*)\);\s*$')
        {
            $paramTypes = @()
            foreach ($raw in (Split-TopLevel $Matches[3]))
            {
                if ($raw.Length -eq 0) { continue }
                $clean = ($raw -replace '\s*=\s*.+$', '') -replace '^(out|ref)\s+', ''
                $typeText = $clean -replace '\s+\w+$', ''
                $paramTypes += (ConvertTo-ClrName $typeText)
            }
            $members.Add([pscustomobject]@{ Name = $Matches[2]; Params = $paramTypes })
        }
    }
    return , $members.ToArray()
}

function Get-ParamClrName([Reflection.ParameterInfo]$parameter)
{
    return ($parameter.ParameterType.Name -replace '&$', '')
}

function Test-InterfaceMembers([Type]$interfaceType, $stubMembers)
{
    $real = @($interfaceType.GetMethods())
    foreach ($inherited in $interfaceType.GetInterfaces()) { $real += @($inherited.GetMethods()) }

    foreach ($member in $stubMembers)
    {
        $arity = @($member.Params).Count
        $named = @($real | Where-Object { $_.Name -eq $member.Name -and @($_.GetParameters()).Count -eq $arity })
        $exact = $null
        foreach ($candidate in $named)
        {
            $names = @($candidate.GetParameters() | ForEach-Object { Get-ParamClrName $_ })
            if (($names -join '|') -eq (@($member.Params) -join '|')) { $exact = $candidate; break }
        }
        if ($null -ne $exact)
        {
            $typeList = (@($exact.GetParameters() | ForEach-Object { Get-ParamClrName $_ })) -join ','
            Write-Output ('OK ' + $exact.ReturnType.Name + ' ' + $member.Name + '(' + $typeList + ')')
        }
        elseif ($named.Count -gt 0)
        {
            Write-Drift ($member.Name + '/' + $arity + ': parameter types differ from the real interface')
        }
        else
        {
            Write-Drift ($member.Name + '/' + $arity + ': not found in real interface')
        }
    }
}

function Test-BaseClassMembers([Type]$baseType)
{
    foreach ($method in @('Init', 'Dispose', 'Execute'))
    {
        if ($null -ne $baseType.GetMethod($method)) { Write-Output ('OK CPHInlineBase.' + $method) }
        else { Write-Drift ('CPHInlineBase.' + $method) }
    }
    foreach ($property in @('CPH', 'args'))
    {
        if ($null -ne $baseType.GetProperty($property)) { Write-Output ('OK CPHInlineBase.' + $property) }
        else { Write-Drift ('CPHInlineBase.' + $property) }
    }
}

$stubPath = Join-Path $PSScriptRoot 'compile-check\Stub\CphStub.cs'
$stubMembers = Read-StubInterface $stubPath
if (@($stubMembers).Count -eq 0)
{
    Write-Drift 'stub: no interface members could be parsed from CphStub.cs'
}

$pluginPath = Join-Path $script:SbDir 'Streamer.bot.Plugin.Interface.dll'
$plugin = [Reflection.Assembly]::ReflectionOnlyLoadFrom($pluginPath)
$exported = Get-ExportedTypesSafe $plugin

$interfaceType = $exported | Where-Object { $_.Name -eq 'IInlineInvokeProxy' } | Select-Object -First 1
if ($null -eq $interfaceType) { Write-Drift 'IInlineInvokeProxy: type not found' }
else { Test-InterfaceMembers $interfaceType $stubMembers }

$baseType = $exported | Where-Object { $_.Name -eq 'CPHInlineBase' } | Select-Object -First 1
if ($null -eq $baseType) { Write-Drift 'CPHInlineBase: type not found' }
else { Test-BaseClassMembers $baseType }

if ($Facts)
{
    $commonPath = Join-Path $script:SbDir 'Streamer.bot.Common.dll'
    $common = [Reflection.Assembly]::ReflectionOnlyLoadFrom($commonPath)
    $eventType = $common.GetType('Streamer.bot.Common.Events.EventType')
    if ($null -eq $eventType) { Write-Drift 'EventType: type not found' }
    else
    {
        foreach ($name in @('StreamerbotStarted', 'StreamerbotExiting', 'CustomEvent', 'CustomCodeEvent'))
        {
            $field = $eventType.GetField($name)
            if ($null -eq $field) { Write-Drift ('EventType.' + $name + ': not found'); continue }
            $value = [Convert]::ToInt64($field.GetRawConstantValue())
            Write-Output ('Streamer.bot.Common.Events.EventType.' + $name + ' = ' + $value)
        }
    }

    foreach ($file in @('Streamer.bot.exe', 'Newtonsoft.Json.dll', 'Microsoft.CodeAnalysis.CSharp.dll'))
    {
        $info = [Diagnostics.FileVersionInfo]::GetVersionInfo((Join-Path $script:SbDir $file))
        Write-Output ('FileVersion ' + $file + ' = ' + $info.FileVersion)
        Write-Output ('ProductVersion ' + $file + ' = ' + $info.ProductVersion)
    }
}

if ($script:DriftCount -gt 0) { exit 1 }
exit 0
