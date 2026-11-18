#Requires -Version 7.0

param(
    [Parameter(Mandatory)] [string]$Batch,
    [string]$Cli,
    [string]$Python = 'python'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-BatchDiagnostic([string]$Message) {
    $diagnostic = @{
        schema_version = 1
        event = 'diagnostic'
        level = 'error'
        message = $Message
    }
    [Console]::Error.WriteLine(($diagnostic | ConvertTo-Json -Compress -EscapeHandling EscapeNonAscii))
}

try {
    $batchPath = (Get-Item -LiteralPath $Batch).FullName
    $directory = [IO.Path]::GetDirectoryName($batchPath)
    $items = Get-Content -LiteralPath $batchPath -Raw -Encoding utf8 |
        ConvertFrom-Json -AsHashtable -NoEnumerate
    if ($items -isnot [array] -or $items.Count -eq 0) {
        throw 'Expected a nonempty JSON list of export jobs.'
    }
    $jobs = for ($index = 0; $index -lt $items.Count; $index++) {
        $item = $items[$index]
        $number = $index + 1
        if ($item -isnot [System.Collections.IDictionary]) {
            throw "Job $number must be a JSON object."
        }
        if ($item['project'] -isnot [string] -or [string]::IsNullOrWhiteSpace($item['project'])) {
            throw "Job $number requires a project path."
        }
        if ($item['output'] -isnot [string] -or [string]::IsNullOrWhiteSpace($item['output'])) {
            throw "Job $number requires an output path."
        }
        $layer = if ($item.Contains('layer')) { $item['layer'] } else { 'sky' }
        if ($layer -isnot [string] -or $layer -cnotin @('sky', 'foreground', 'composition')) {
            throw "Job $number has an invalid layer."
        }
        $band = $item['band']
        if ($null -ne $band -and ($band -isnot [string] -or [string]::IsNullOrWhiteSpace($band) -or $layer -cne 'sky')) {
            throw "Job $number requires a nonempty band and the sky layer."
        }
        @{
            Project = [IO.Path]::GetFullPath($item['project'], $directory)
            Output = [IO.Path]::GetFullPath($item['output'], $directory)
            Layer = $layer
            Band = $band
        }
    }
} catch {
    Write-BatchDiagnostic $_.Exception.Message
    exit 2
}

$registered = $false
$batchCode = 0
try {
    if ($IsWindows -and -not ('AstroMosaicBatchInterrupt' -as [type])) {
        # Keep the shell alive while the child receives the same console event and cleans up.
        Add-Type -TypeDefinition @'
using System.ComponentModel;
using System.Runtime.InteropServices;

public static class AstroMosaicBatchInterrupt
{
    private delegate bool ControlHandler(uint control);
    private static readonly ControlHandler Handler = Cancel;
    private static volatile bool requested;
    public static bool Requested => requested;

    [DllImport("kernel32.dll")]
    private static extern uint GetConsoleCP();

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool SetConsoleCtrlHandler(ControlHandler handler, bool add);

    private static bool Cancel(uint control)
    {
        if (control != 0 && control != 1) return false;
        requested = true;
        return true;
    }

    public static bool Install()
    {
        requested = false;
        if (GetConsoleCP() == 0) return false;
        if (!SetConsoleCtrlHandler(Handler, true)) throw new Win32Exception();
        return true;
    }

    public static void Uninstall()
    {
        if (!SetConsoleCtrlHandler(Handler, false)) throw new Win32Exception();
    }
}
'@
    }
    if ($IsWindows) {
        $registered = [AstroMosaicBatchInterrupt]::Install()
    }
    $program = if ($Cli) { $Cli } else { $Python }
    $executable = if (Test-Path -LiteralPath $program -PathType Leaf) {
        (Get-Item -LiteralPath $program).FullName
    } else {
        (Get-Command -Name $program -CommandType Application | Select-Object -First 1).Source
    }
    $prefix = if (-not $Cli) { '-m', 'astromosaic' }
    $expectedStatus = @{ 0 = 'ok'; 1 = 'error'; 130 = 'cancelled' }

    foreach ($job in $jobs) {
        if ($registered -and [AstroMosaicBatchInterrupt]::Requested) {
            $batchCode = 130
            break
        }
        $start = [Diagnostics.ProcessStartInfo]::new($executable)
        $start.UseShellExecute = $false
        $start.RedirectStandardOutput = $true
        $start.StandardOutputEncoding = [Text.UTF8Encoding]::new($false)
        foreach ($argument in $prefix + @(
            'project', 'export', $job.Project, '-o', $job.Output,
            '--layer', $job.Layer, '--json', '--progress'
        )) {
            $start.ArgumentList.Add($argument)
        }
        if ($null -ne $job.Band) {
            $start.ArgumentList.Add("--band=$($job.Band)")
        }

        $child = [Diagnostics.Process]::Start($start)
        try {
            $reportLine = $child.StandardOutput.ReadToEnd().Trim()
            $child.WaitForExit()
            $childCode = $child.ExitCode
        } finally {
            $child.Dispose()
        }

        $interrupted = $registered -and [AstroMosaicBatchInterrupt]::Requested
        if ($interrupted -and -not $reportLine) {
            $batchCode = 130
            break
        }
        $report = ConvertFrom-Json -InputObject $reportLine -AsHashtable
        if (
            -not $expectedStatus.ContainsKey($childCode) -or
            $report -isnot [System.Collections.IDictionary] -or
            $report['schema_version'] -ne 1 -or
            $report['command'] -cne 'project export' -or
            $report['status'] -cne $expectedStatus[$childCode]
        ) {
            throw 'The CLI returned an unexpected project export result.'
        }
        Write-Output $reportLine
        if ($interrupted -or $childCode -eq 130) {
            $batchCode = 130
            break
        }
        if ($childCode -ne 0) {
            $batchCode = 1
        }
    }
} catch {
    Write-BatchDiagnostic "Batch export stopped. $($_.Exception.Message)"
    $batchCode = 1
} finally {
    if ($registered) {
        [AstroMosaicBatchInterrupt]::Uninstall()
    }
}
exit $batchCode
