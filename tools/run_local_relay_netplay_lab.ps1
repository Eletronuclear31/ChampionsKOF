param(
    [string]$SessionId = ("local-relay-{0}" -f (Get-Date -Format "yyyyMMdd-HHmmss")),
    [string]$ExePath,
    [string]$Driver = "kof2002",
    [string]$GameZip,
    [string]$BiosZip,
    [string]$RomDir,
    [int]$DurationSeconds = 120,
    [int]$HttpPort = 0,
    [int]$RelayPort = 0,
    [int]$SimulatedLatencyMs = 0,
    [int]$SimulatedJitterMs = 0,
    [int]$SimulatedLossPercent = 0,
    [int]$ClientSimulatedLatencyMs = -1,
    [int]$ClientSimulatedJitterMs = -1,
    [int]$ClientSimulatedLossPercent = -1,
    [string]$ReportRoot = "C:\Users\Marcus\Desktop\netplay_local_relay_lab",
    [switch]$SkipBuild,
    [switch]$RuntimeTelemetry,
    [switch]$DeepTrace,
    [switch]$ScriptedInputs,
    [switch]$NoTrace,
    [switch]$UltraLightTrace,
    [switch]$NoDebugOverlay,
    [switch]$PublicServer,
    [string]$PublicBaseUrl = "http://a2da96080798c382c.awsglobalaccelerator.com:8080",
    [string]$PublicRelayHost = "a2da96080798c382c.awsglobalaccelerator.com",
    [int]$PublicRelayPort = 7000,
    [int]$MinInputDelayFrames = -1,
    [int]$MaxInputDelayFrames = -1,
    [int]$P1NetplayListenPort = 56101,
    [int]$P2NetplayListenPort = 56102,
    [string]$ViewportBackend = "",
    [int]$RenderFilter = -1,
    [switch]$AllowP2P,
    [switch]$ForceDirectLab
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-RepoRoot {
    return (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
}

function New-CleanDirectory {
    param([string]$Path)

    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
    return (Resolve-Path -LiteralPath $Path).Path
}

function ConvertTo-ProcessArguments {
    param([string[]]$Arguments)

    $quoted = foreach ($arg in $Arguments) {
        if ($null -eq $arg) {
            '""'
            continue
        }
        $text = [string]$arg
        if ($text.Length -eq 0) {
            '""'
            continue
        }
        if ($text -notmatch '[\s"]') {
            $text
            continue
        }
        '"' + ($text -replace '\\(?=\\*")', '$&$&' -replace '"', '\"') + '"'
    }
    return ($quoted -join " ")
}

function Resolve-LabExe {
    param(
        [string]$RootDir,
        [string]$ExplicitPath
    )

    if (-not [string]::IsNullOrWhiteSpace($ExplicitPath)) {
        return (Resolve-Path -LiteralPath $ExplicitPath).Path
    }

    $candidates = @(
        (Join-Path $RootDir "out\build-msvc-release\FBNeoLibTester.exe"),
        (Join-Path $RootDir "out\build-msvc-release\ChampionsKOFEmulator.exe"),
        (Join-Path $RootDir "build\Release\FBNeoLibTester.exe"),
        (Join-Path $RootDir "build\Release\ChampionsKOFEmulator.exe")
    )

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    throw "Nao encontrei executavel local. Compile primeiro ou use -ExePath."
}

function Resolve-RomSet {
    param(
        [string]$RootDir,
        [string]$ExeDir,
        [string]$DriverName,
        [string]$ExplicitGameZip,
        [string]$ExplicitBiosZip,
        [string]$ExplicitRomDir
    )

    if (-not [string]::IsNullOrWhiteSpace($ExplicitGameZip) -and
        -not [string]::IsNullOrWhiteSpace($ExplicitBiosZip)) {
        $game = (Resolve-Path -LiteralPath $ExplicitGameZip).Path
        $bios = (Resolve-Path -LiteralPath $ExplicitBiosZip).Path
        $dir = if (-not [string]::IsNullOrWhiteSpace($ExplicitRomDir)) {
            (Resolve-Path -LiteralPath $ExplicitRomDir).Path
        } else {
            Split-Path -Path $game -Parent
        }
        return [pscustomobject]@{ GameZip = $game; BiosZip = $bios; RomDir = $dir }
    }

    if (-not [string]::IsNullOrWhiteSpace($ExplicitRomDir)) {
        $dir = (Resolve-Path -LiteralPath $ExplicitRomDir).Path
        $game = Join-Path $dir ("{0}.zip" -f $DriverName.Trim().ToLowerInvariant())
        $bios = Join-Path $dir "neogeo.zip"
        if ((Test-Path -LiteralPath $game) -and (Test-Path -LiteralPath $bios)) {
            return [pscustomobject]@{ GameZip = (Resolve-Path -LiteralPath $game).Path; BiosZip = (Resolve-Path -LiteralPath $bios).Path; RomDir = $dir }
        }
    }

    $normalizedDriver = if ([string]::IsNullOrWhiteSpace($DriverName)) { "kof2002" } else { $DriverName.Trim().ToLowerInvariant() }
    $candidateDirs = @(
        (Join-Path $ExeDir "roms"),
        (Join-Path $ExeDir "..\roms"),
        (Join-Path $ExeDir "..\..\roms"),
        (Join-Path $RootDir "roms"),
        (Join-Path $RootDir "out\ChampionsKOF-Offline\roms"),
        (Join-Path $RootDir "out\ChampionsKOF-Release\roms"),
        "C:\Users\Marcus\Documents\ChampionsKOF\assets\kof2002",
        "C:\Users\Marcus\Documents\ChampionsKOF\assets\kof98"
    )

    $seen = @{}
    foreach ($candidate in $candidateDirs) {
        $fullDir = [System.IO.Path]::GetFullPath($candidate)
        $key = $fullDir.ToLowerInvariant()
        if ($seen.ContainsKey($key)) {
            continue
        }
        $seen[$key] = $true

        $game = Join-Path $fullDir ("{0}.zip" -f $normalizedDriver)
        $bios = Join-Path $fullDir "neogeo.zip"
        if ((Test-Path -LiteralPath $game) -and (Test-Path -LiteralPath $bios)) {
            return [pscustomobject]@{
                GameZip = (Resolve-Path -LiteralPath $game).Path
                BiosZip = (Resolve-Path -LiteralPath $bios).Path
                RomDir = (Resolve-Path -LiteralPath $fullDir).Path
            }
        }
    }

    throw "Nao encontrei {0}.zip e neogeo.zip. Informe -GameZip/-BiosZip ou -RomDir." -f $normalizedDriver
}

function Resolve-Python {
    param([string]$RootDir)

    $venvPython = Join-Path $RootDir "online_server\.venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venvPython) {
        return (Resolve-Path -LiteralPath $venvPython).Path
    }
    return "python"
}

function Invoke-LoggedProcess {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$WorkingDirectory,
        [string]$OutputPath,
        [int]$TimeoutSeconds = 180
    )

    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $FilePath
    $psi.WorkingDirectory = $WorkingDirectory
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.Arguments = ConvertTo-ProcessArguments -Arguments $Arguments

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $psi
    [void]$process.Start()

    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        try { $process.Kill() } catch {}
        throw "Timeout executando $FilePath $($Arguments -join ' ')"
    }

    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $content = @()
    $content += "COMMAND $FilePath $($Arguments -join ' ')"
    $content += "EXIT_CODE $($process.ExitCode)"
    $content += "STDOUT_BEGIN"
    $content += $stdout.TrimEnd()
    $content += "STDOUT_END"
    $content += "STDERR_BEGIN"
    $content += $stderr.TrimEnd()
    $content += "STDERR_END"
    $content -join [Environment]::NewLine | Set-Content -LiteralPath $OutputPath -Encoding UTF8

    return [pscustomobject]@{ ExitCode = $process.ExitCode; OutputPath = $OutputPath }
}

function Start-LoggedBackgroundProcess {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$WorkingDirectory,
        [string]$StdoutPath,
        [string]$StderrPath,
        [hashtable]$Environment = @{}
    )

    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $FilePath
    $psi.WorkingDirectory = $WorkingDirectory
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.Arguments = ConvertTo-ProcessArguments -Arguments $Arguments
    foreach ($key in $Environment.Keys) {
        $psi.EnvironmentVariables[[string]$key] = [string]$Environment[$key]
    }

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $psi
    [void]$process.Start()
    return [pscustomobject]@{
        Process = $process
        StdoutPath = $StdoutPath
        StderrPath = $StderrPath
    }
}

function Save-ProcessOutput {
    param([object]$Handle)

    if ($null -eq $Handle -or $null -eq $Handle.Process) {
        return
    }
    try {
        $stdout = $Handle.Process.StandardOutput.ReadToEnd()
        $stderr = $Handle.Process.StandardError.ReadToEnd()
        Set-Content -LiteralPath $Handle.StdoutPath -Value $stdout -Encoding UTF8
        Set-Content -LiteralPath $Handle.StderrPath -Value $stderr -Encoding UTF8
    } catch {}
}

function Stop-ProcessHandle {
    param([object]$Handle)

    if ($null -eq $Handle -or $null -eq $Handle.Process) {
        return
    }
    if (-not $Handle.Process.HasExited) {
        try { $Handle.Process.Kill() } catch {}
    }
    try { [void]$Handle.Process.WaitForExit(5000) } catch {}
    Save-ProcessOutput -Handle $Handle
}

function Read-PerfLine {
    param(
        [string]$Path,
        [string]$Prefix,
        [string]$FallbackPrefix = ""
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return ""
    }

    $line = Get-Content -LiteralPath $Path | Where-Object { $_ -like "$Prefix=*" } | Select-Object -First 1
    if ($null -eq $line -and -not [string]::IsNullOrWhiteSpace($FallbackPrefix)) {
        $line = Get-Content -LiteralPath $Path | Where-Object { $_ -like "$FallbackPrefix=*" } | Select-Object -First 1
    }
    if ($null -eq $line) {
        return ""
    }
    return [string]$line
}

function Read-PerfMetricField {
    param(
        [string]$Path,
        [string]$Prefix,
        [string]$Field,
        [string]$FallbackPrefix = ""
    )

    $line = Read-PerfLine -Path $Path -Prefix $Prefix -FallbackPrefix $FallbackPrefix
    if ([string]::IsNullOrWhiteSpace($line)) {
        return $null
    }

    $match = [regex]::Match($line, "\b$([regex]::Escape($Field))=([0-9]+(?:[\.,][0-9]+)?)ms")
    if (-not $match.Success) {
        return $null
    }

    return [double]::Parse($match.Groups[1].Value.Replace(",", "."), [System.Globalization.CultureInfo]::InvariantCulture)
}

function Read-PerfIntegerField {
    param(
        [string]$Path,
        [string]$Prefix
    )

    $line = Read-PerfLine -Path $Path -Prefix $Prefix
    if ([string]::IsNullOrWhiteSpace($line)) {
        return $null
    }

    $match = [regex]::Match($line, "=(\d+)")
    if (-not $match.Success) {
        return $null
    }

    return [int]$match.Groups[1].Value
}

function Format-NullableMs {
    param([object]$Value)

    if ($null -eq $Value) {
        return "n/a"
    }
    return ("{0:N3}ms" -f ([double]$Value))
}

function Get-FrameSpikeDigest {
    param([string]$LogsPath)

    $path = Join-Path $LogsPath "frame_spikes.log"
    if (-not (Test-Path -LiteralPath $path)) {
        return [pscustomobject]@{
            Exists = $false
            Count = 0
            TopCauses = ""
            MaxWorstMs = $null
            FirstLine = ""
        }
    }

    $lines = @(Get-Content -LiteralPath $path)
    $causeCounts = @{}
    $maxWorst = $null
    foreach ($line in $lines) {
        $causeMatch = [regex]::Match($line, "cause=([^|]+)")
        if ($causeMatch.Success) {
            $cause = $causeMatch.Groups[1].Value.Trim()
            if (-not $causeCounts.ContainsKey($cause)) {
                $causeCounts[$cause] = 0
            }
            $causeCounts[$cause]++
        }
        $worstMatch = [regex]::Match($line, "worstMs=([0-9]+(?:[\.,][0-9]+)?)")
        if ($worstMatch.Success) {
            $worst = [double]::Parse($worstMatch.Groups[1].Value.Replace(",", "."), [System.Globalization.CultureInfo]::InvariantCulture)
            if ($null -eq $maxWorst -or $worst -gt $maxWorst) {
                $maxWorst = $worst
            }
        }
    }

    $top = $causeCounts.GetEnumerator() |
        Sort-Object -Property Value -Descending |
        Select-Object -First 3 |
        ForEach-Object { "{0} x{1}" -f $_.Key, $_.Value }

    return [pscustomobject]@{
        Exists = $true
        Count = $lines.Count
        TopCauses = ($top -join "; ")
        MaxWorstMs = $maxWorst
        FirstLine = if ($lines.Count -gt 0) { $lines[0] } else { "" }
    }
}

function Get-PerfCauseDiagnosis {
    param(
        [string]$Role,
        [string]$RootPath,
        [string]$LogsPath,
        [bool]$TraceDisabled
    )

    $perfPath = Join-Path $RootPath "perf_report.log"
    $frameP95 = Read-PerfMetricField -Path $perfPath -Prefix "stableFrameTimeMs" -Field "p95"
    $frameP99 = Read-PerfMetricField -Path $perfPath -Prefix "stableFrameTimeMs" -Field "p99"
    $frameMax = Read-PerfMetricField -Path $perfPath -Prefix "stableFrameTimeMs" -Field "max"
    $updateP95 = Read-PerfMetricField -Path $perfPath -Prefix "stableUpdateFrameMs" -FallbackPrefix "update_frame" -Field "p95"
    $updateP99 = Read-PerfMetricField -Path $perfPath -Prefix "stableUpdateFrameMs" -FallbackPrefix "update_frame" -Field "p99"
    $renderP95 = Read-PerfMetricField -Path $perfPath -Prefix "stableRenderSubmitMs" -FallbackPrefix "render_submit" -Field "p95"
    $audioUnderruns = Read-PerfIntegerField -Path $perfPath -Prefix "audioUnderrunCount"
    $schedulerP95 = Read-PerfMetricField -Path $perfPath -Prefix "schedulerOversleepMs" -Field "p95"
    $timerJitterP95 = Read-PerfMetricField -Path $perfPath -Prefix "timer_jitter_vs_budget" -Field "p95"
    $deadlineMissP95 = Read-PerfMetricField -Path $perfPath -Prefix "deadline_miss" -Field "p95"
    $netplayAdvanceP95 = Read-PerfMetricField -Path $perfPath -Prefix "netplay_advance" -Field "p95"
    $netplayPumpP95 = Read-PerfMetricField -Path $perfPath -Prefix "netplay_pump" -Field "p95"
    $normalAdvanceP95 = Read-PerfMetricField -Path $perfPath -Prefix "netplay_normal_advance" -Field "p95"
    $authApplyP95 = Read-PerfMetricField -Path $perfPath -Prefix "netplay_authoritative_apply" -Field "p95"
    $hitches = Read-PerfIntegerField -Path $perfPath -Prefix "stableHitchCount"
    $spikes = Get-FrameSpikeDigest -LogsPath $LogsPath

    $tags = New-Object System.Collections.Generic.List[string]
    $severity = "OK"
    if ($null -eq $frameP95 -or $null -eq $updateP95 -or $null -eq $renderP95) {
        $severity = "INCONCLUSIVO"
        $tags.Add("metricas-incompletas") | Out-Null
    } else {
        if ($frameP95 -gt 19.0 -or $updateP95 -gt 6.0 -or $renderP95 -gt 2.0 -or ($null -ne $audioUnderruns -and $audioUnderruns -gt 0)) {
            $severity = "CRITICO"
        } elseif ($frameP95 -gt 18.0 -or $updateP95 -gt 4.0 -or $renderP95 -gt 1.0) {
            $severity = "ATENCAO"
        }

        if ($null -ne $audioUnderruns -and $audioUnderruns -gt 0) {
            $tags.Add("audio-underrun") | Out-Null
        }
        if ($renderP95 -gt 1.0) {
            $tags.Add("render-present") | Out-Null
        }
        if ($updateP95 -gt 4.0) {
            if ($null -ne $netplayAdvanceP95 -and $netplayAdvanceP95 -gt 3.0) {
                $tags.Add("netplay-advance/rollback") | Out-Null
            } else {
                $tags.Add("update-frame") | Out-Null
            }
        }
        if ($null -ne $normalAdvanceP95 -and $normalAdvanceP95 -gt 2.0) {
            $tags.Add("normal-advance") | Out-Null
        }
        if ($null -ne $netplayPumpP95 -and $netplayPumpP95 -gt 2.0) {
            $tags.Add("udp-pump") | Out-Null
        }
        if (($null -ne $schedulerP95 -and $schedulerP95 -gt 6.0) -or
            ($null -ne $timerJitterP95 -and $timerJitterP95 -gt 6.0) -or
            ($null -ne $deadlineMissP95 -and $deadlineMissP95 -gt 1.0)) {
            $tags.Add("scheduler/wake") | Out-Null
        }
        if (($null -ne $hitches -and $hitches -gt 0) -and $frameP95 -gt 18.0) {
            $tags.Add("hitches-estaveis") | Out-Null
        }
        if ($TraceDisabled -and ($frameP95 -gt 18.0 -or $updateP95 -gt 4.0)) {
            $tags.Add("repetir-com-ultralight-trace") | Out-Null
        }
    }

    if ($tags.Count -eq 0) {
        $tags.Add("sem-gargalo-relevante") | Out-Null
    }

    return [pscustomobject]@{
        Role = $Role
        Severity = $severity
        Tags = ($tags -join ", ")
        FrameP95 = $frameP95
        FrameP99 = $frameP99
        FrameMax = $frameMax
        UpdateP95 = $updateP95
        UpdateP99 = $updateP99
        RenderP95 = $renderP95
        AudioUnderruns = $audioUnderruns
        SchedulerP95 = $schedulerP95
        TimerJitterP95 = $timerJitterP95
        DeadlineMissP95 = $deadlineMissP95
        NetplayAdvanceP95 = $netplayAdvanceP95
        NetplayPumpP95 = $netplayPumpP95
        NormalAdvanceP95 = $normalAdvanceP95
        AuthApplyP95 = $authApplyP95
        StableHitches = $hitches
        SpikeCount = $spikes.Count
        SpikeTopCauses = $spikes.TopCauses
        SpikeMaxWorstMs = $spikes.MaxWorstMs
    }
}

function Invoke-JsonApi {
    param(
        [string]$Method,
        [string]$Uri,
        [object]$Body = $null,
        [string]$Token = ""
    )

    $headers = @{}
    if (-not [string]::IsNullOrWhiteSpace($Token)) {
        $headers["Authorization"] = "Bearer $Token"
    }
    $params = @{
        Method = $Method
        Uri = $Uri
        Headers = $headers
        TimeoutSec = 20
    }
    if ($null -ne $Body) {
        $params["ContentType"] = "application/json"
        $params["Body"] = ($Body | ConvertTo-Json -Depth 8)
    }
    return Invoke-RestMethod @params
}

function New-LabHardwareId {
    param([string]$Seed)

    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Seed)
        $hash = $sha.ComputeHash($bytes)
        return (($hash | ForEach-Object { $_.ToString("x2") }) -join "")
    } finally {
        $sha.Dispose()
    }
}

function Wait-HttpReady {
    param(
        [string]$BaseUrl,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $lastError = $null
    while ((Get-Date) -lt $deadline) {
        try {
            Invoke-JsonApi -Method "GET" -Uri "$BaseUrl/api/bootstrap" | Out-Null
            return
        } catch {
            $lastError = $_
            Start-Sleep -Milliseconds 300
        }
    }
    throw "Servidor local nao respondeu em $BaseUrl. Ultimo erro: $lastError"
}

function Summarize-TraceFile {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return [pscustomobject]@{
            Exists = $false
            Lines = 0
            MismatchLines = 0
            FatalLines = 0
            ResyncLines = 0
            FirstImportant = ""
            MaxFrame = -1
            ActiveFrameLines = 0
            RunningStateLines = 0
            WaitingPeerLines = 0
            MaxDelay = -1
            MaxAdaptiveDelay = -1
            MaxJitterBuffer = -1
        }
    }

    $lines = Get-Content -LiteralPath $Path
    $important = $lines | Where-Object {
        $_ -match "state-mismatch|mismatch-state|desync|resync-|canonical-restart|canonical-rebase|state-resync|sync-fence|state-recovery-limit|fatal=(?!---)"
    }
    $maxFrame = -1
    $activeFrameLines = 0
    $maxDelay = -1
    $maxAdaptiveDelay = -1
    $maxJitterBuffer = -1
    foreach ($line in $lines) {
        if ($line -match "\bframe=(-?\d+)") {
            $frame = [int]$Matches[1]
            $maxFrame = [Math]::Max($maxFrame, $frame)
            if ($frame -gt 0) {
                $activeFrameLines++
            }
        }
        $delayMatch = [regex]::Match($line, "\bdelay=(-?\d+)")
        if ($delayMatch.Success) {
            $maxDelay = [Math]::Max($maxDelay, [int]$delayMatch.Groups[1].Value)
        }
        $adaptiveDelayMatch = [regex]::Match($line, "\badaptiveDelay=(-?\d+)")
        if ($adaptiveDelayMatch.Success) {
            $maxAdaptiveDelay = [Math]::Max($maxAdaptiveDelay, [int]$adaptiveDelayMatch.Groups[1].Value)
        }
        $jitterBufferMatch = [regex]::Match($line, "\bjitterBuffer=(-?\d+)")
        if ($jitterBufferMatch.Success) {
            $maxJitterBuffer = [Math]::Max($maxJitterBuffer, [int]$jitterBufferMatch.Groups[1].Value)
        }
    }
    return [pscustomobject]@{
        Exists = $true
        Lines = $lines.Count
        MismatchLines = @($lines | Where-Object { $_ -match "state-mismatch|mismatch-state|mismatch-telemetry|mismatch-input|mismatch-area|desync" }).Count
        FatalLines = @($lines | Where-Object { $_ -match "fatal=(?!---)|\[fatal" }).Count
        ResyncLines = @($lines | Where-Object { $_ -match "resync-|state-resync|sync-fence|state-recovery-limit|canonical-restart|canonical-rebase" }).Count
        FirstImportant = @($important | Select-Object -First 1) -join ""
        MaxFrame = $maxFrame
        ActiveFrameLines = $activeFrameLines
        MaxDelay = $maxDelay
        MaxAdaptiveDelay = $maxAdaptiveDelay
        MaxJitterBuffer = $maxJitterBuffer
        RunningStateLines = @($lines | Where-Object { $_ -match "state=Running|state=Synchronizing|state=Resynchronizing|state=Recovering" }).Count
        WaitingPeerLines = @($lines | Where-Object { $_ -match "state=WaitingPeer|Aguardando_jogador" }).Count
    }
}

$repoRoot = Resolve-RepoRoot
$sessionRoot = New-CleanDirectory (Join-Path $ReportRoot $SessionId)
$summaryPath = Join-Path $sessionRoot "summary.md"
$serverData = if ($PublicServer.IsPresent) { Join-Path $sessionRoot "server-data" } else { New-CleanDirectory (Join-Path $sessionRoot "server-data") }
$guiRoot = New-CleanDirectory (Join-Path $sessionRoot "gui")
$serverHandle = $null
$p1Handle = $null
$p2Handle = $null
$endpointBackupPath = $null
$endpointPath = $null
$endpointHadExistingFile = $false

try {
    Write-Host "Sessao: $SessionId"
    Write-Host "Relatorios: $sessionRoot"

    if (-not $SkipBuild.IsPresent) {
        Write-Host "Compilando build Release..."
        $buildResult = Invoke-LoggedProcess `
            -FilePath "cmake" `
            -Arguments @("--build", (Join-Path $repoRoot "out\build-msvc-release"), "--config", "Release") `
            -WorkingDirectory $repoRoot `
            -OutputPath (Join-Path $sessionRoot "build.log") `
            -TimeoutSeconds 900
        if ($buildResult.ExitCode -ne 0) {
            throw "Build falhou. Veja $($buildResult.OutputPath)"
        }
    }

    $exe = Resolve-LabExe -RootDir $repoRoot -ExplicitPath $ExePath
    $exeDir = Split-Path -Path $exe -Parent
    $romSet = Resolve-RomSet -RootDir $repoRoot -ExeDir $exeDir -DriverName $Driver -ExplicitGameZip $GameZip -ExplicitBiosZip $BiosZip -ExplicitRomDir $RomDir
    $python = Resolve-Python -RootDir $repoRoot
    if ($HttpPort -le 0) {
        $HttpPort = Get-Random -Minimum 18100 -Maximum 18900
    }
    if ($RelayPort -le 0) {
        $RelayPort = Get-Random -Minimum 52100 -Maximum 52900
    }
    $SimulatedLatencyMs = [Math]::Max(0, $SimulatedLatencyMs)
    $SimulatedJitterMs = [Math]::Max(0, $SimulatedJitterMs)
    $SimulatedLossPercent = [Math]::Max(0, [Math]::Min(100, $SimulatedLossPercent))
    $ClientSimulatedLatencyMs = [Math]::Max(-1, $ClientSimulatedLatencyMs)
    $ClientSimulatedJitterMs = [Math]::Max(-1, $ClientSimulatedJitterMs)
    $ClientSimulatedLossPercent = [Math]::Max(-1, [Math]::Min(100, $ClientSimulatedLossPercent))
    $baseUrl = if ($PublicServer.IsPresent) { $PublicBaseUrl.TrimEnd("/") } else { "http://127.0.0.1:$HttpPort" }
    $relayHostForClients = if ($PublicServer.IsPresent) { $PublicRelayHost.Trim() } else { "127.0.0.1" }
    $relayPortForClients = if ($PublicServer.IsPresent) { $PublicRelayPort } else { $RelayPort }

    if (-not $PublicServer.IsPresent) {
        $endpointPath = Join-Path $exeDir "network_endpoints.json"
        $endpointBackupPath = Join-Path $sessionRoot "network_endpoints.original.json"
        if (Test-Path -LiteralPath $endpointPath) {
            $endpointHadExistingFile = $true
            Copy-Item -LiteralPath $endpointPath -Destination $endpointBackupPath -Force
        }
        $labEndpoints = [ordered]@{
            matchmaking_urls = @("$baseUrl/")
            relays = @(
                [ordered]@{
                    id = "local-lab"
                    host = $relayHostForClients
                    port = $relayPortForClients
                    region = "local"
                    role = "primary"
                    primary = $true
                    enabled = $true
                }
            )
        }
        $labEndpoints |
            ConvertTo-Json -Depth 8 |
            Set-Content -LiteralPath $endpointPath -Encoding UTF8
    }

    if ($PublicServer.IsPresent) {
        Write-Host "Servidor publico HTTP $baseUrl, relay UDP ${relayHostForClients}:$relayPortForClients..."
        Wait-HttpReady -BaseUrl $baseUrl -TimeoutSeconds 45
    } else {
        Write-Host "Servidor local HTTP $HttpPort, relay UDP $RelayPort..."
        $serverHandle = Start-LoggedBackgroundProcess `
            -FilePath $python `
            -Arguments @((Join-Path $repoRoot "online_server\server.py"),
                         "--host", "127.0.0.1",
                         "--port", "$HttpPort",
                         "--relay-host", "127.0.0.1",
                         "--relay-port", "$RelayPort",
                         "--public-relay-host", "127.0.0.1",
                         "--public-relay-port", "$RelayPort",
                         "--lab-relay-latency-ms", "$SimulatedLatencyMs",
                         "--lab-relay-jitter-ms", "$SimulatedJitterMs",
                         "--lab-relay-loss-percent", "$SimulatedLossPercent",
                         "--data-dir", $serverData) `
            -WorkingDirectory (Join-Path $repoRoot "online_server") `
            -StdoutPath (Join-Path $sessionRoot "server_stdout.log") `
            -StderrPath (Join-Path $sessionRoot "server_stderr.log")
        Wait-HttpReady -BaseUrl $baseUrl -TimeoutSeconds 45
    }

    $stamp = Get-Date -Format "yyyyMMddHHmmss"
    $password = "ChampionsLab#2026"
    $p1Register = Invoke-JsonApi -Method "POST" -Uri "$baseUrl/api/auth/register" -Body @{
        full_name = "Relay Lab Player 1"
        nick = "RelayP1-$stamp"
        email = "relay-p1-$stamp@example.local"
        whatsapp = ""
        birth_date = "1990-01-01"
        id_hardware = New-LabHardwareId "relay-lab-$SessionId-p1-$stamp"
        password = $password
    }
    $p2Register = Invoke-JsonApi -Method "POST" -Uri "$baseUrl/api/auth/register" -Body @{
        full_name = "Relay Lab Player 2"
        nick = "RelayP2-$stamp"
        email = "relay-p2-$stamp@example.local"
        whatsapp = ""
        birth_date = "1990-01-01"
        id_hardware = New-LabHardwareId "relay-lab-$SessionId-p2-$stamp"
        password = $password
    }

    $room = Invoke-JsonApi -Method "POST" -Uri "$baseUrl/api/rooms" -Token $p1Register.token -Body @{
        name = "$(if ($PublicServer.IsPresent) { "Public Relay" } else { "Local Relay" }) $SessionId"
        driver = $Driver
        max_players = 2
        target_score = 0
        show_lobby_score = $false
        seat = 1
    }
    $roomId = [string]$room.id
    Invoke-JsonApi -Method "POST" -Uri "$baseUrl/api/rooms/$roomId/join" -Token $p2Register.token -Body @{ seat = 2 } | Out-Null
    Write-Host "Sala: $roomId"

    $durationMs = [Math]::Max(1000, $DurationSeconds * 1000)
    $traceMode = $(if ($NoTrace.IsPresent) { "0" } elseif ($UltraLightTrace.IsPresent) { "ultra" } elseif ($DeepTrace.IsPresent) { "1" } else { "lite" })
    $telemetryForce = $(if ($RuntimeTelemetry.IsPresent -or $DeepTrace.IsPresent) { "1" } else { "0" })
    $stateTraceMode = $(if ($DeepTrace.IsPresent) { "1" } else { "0" })
    $commonEnv = @{
        CHAMPIONS_NETPLAY_TRACE = $traceMode
        CHAMPIONS_NETPLAY_TELEMETRY_FORCE = $telemetryForce
        CHAMPIONS_NETPLAY_STATE_TRACE = $stateTraceMode
        CHAMPIONS_NETPLAY_SCRIPTED_INPUTS = $(if ($ScriptedInputs.IsPresent) { "1" } else { "0" })
    }
    if (-not [string]::IsNullOrWhiteSpace($ViewportBackend)) {
        $commonEnv["CHAMPIONS_VIEWPORT_BACKEND"] = $ViewportBackend.Trim()
    }
    if ($MinInputDelayFrames -ge 0) {
        $commonEnv["CHAMPIONS_NETPLAY_MIN_INPUT_DELAY_FRAMES"] = [string]$MinInputDelayFrames
    }
    if ($MaxInputDelayFrames -ge 0) {
        $commonEnv["CHAMPIONS_NETPLAY_MAX_INPUT_DELAY_FRAMES"] = [string]$MaxInputDelayFrames
    }
    if ($ClientSimulatedLatencyMs -ge 0) {
        $commonEnv["CHAMPIONS_NETPLAY_LAB_TX_LATENCY_MS"] = [string]$ClientSimulatedLatencyMs
    }
    if ($ClientSimulatedJitterMs -ge 0) {
        $commonEnv["CHAMPIONS_NETPLAY_LAB_TX_JITTER_MS"] = [string]$ClientSimulatedJitterMs
    }
    if ($ClientSimulatedLossPercent -ge 0) {
        $commonEnv["CHAMPIONS_NETPLAY_LAB_TX_LOSS_PERCENT"] = [string]$ClientSimulatedLossPercent
    }
    if ($ForceDirectLab.IsPresent) {
        $commonEnv["CHAMPIONS_NETPLAY_LAB_FORCE_DIRECT"] = "1"
    }

    $commonArgs = @(
        "--match-window",
        "--driver", $Driver,
        "--game-zip", $romSet.GameZip,
        "--bios-zip", $romSet.BiosZip,
        "--rom-dir", $romSet.RomDir,
        "--netplay-room", $roomId,
        "--netplay-room-label", "$(if ($PublicServer.IsPresent) { "Public Relay" } else { "Local Relay" }) $SessionId",
        "--netplay-target-score", "0",
        "--netplay-relay-host", $relayHostForClients,
        "--netplay-relay-port", "$relayPortForClients",
        "--perf-report",
        "--perf-duration-ms", "$durationMs"
    )
    if ((-not $AllowP2P.IsPresent) -and (-not $ForceDirectLab.IsPresent)) {
        $commonArgs += "--netplay-force-relay"
    }
    if (-not $NoDebugOverlay.IsPresent) {
        $commonArgs += "--debug-pacing-overlay"
    }

    $p1Root = New-CleanDirectory (Join-Path $guiRoot "p1")
    $p2Root = New-CleanDirectory (Join-Path $guiRoot "p2")
    $logFolder = $(if ($NoTrace.IsPresent -or $UltraLightTrace.IsPresent) { "logs" } else { "server_lab\logs" })
    $p1Logs = New-CleanDirectory (Join-Path $p1Root $logFolder)
    $p2Logs = New-CleanDirectory (Join-Path $p2Root $logFolder)
    $p1Config = New-CleanDirectory (Join-Path $p1Root "config")
    $p2Config = New-CleanDirectory (Join-Path $p2Root "config")

    if ($RenderFilter -ge 0) {
        foreach ($configRoot in @($p1Config, $p2Config)) {
            $settingsDir = Join-Path $configRoot "ChampionsKOF"
            New-Item -ItemType Directory -Force -Path $settingsDir | Out-Null
            Set-Content -LiteralPath (Join-Path $settingsDir "Emulator.ini") -Encoding UTF8 -Value @"
[video]
renderFilter=$RenderFilter
"@
        }
    }

    $p1Args = $commonArgs + @(
        "--netplay-token", $p1Register.token,
        "--netplay-local-username", $p1Register.user.nick,
        "--netplay-user-id", "$($p1Register.user.id)",
        "--netplay-seat", "1",
        "--netplay-listen-port", "$P1NetplayListenPort",
        "--config-dir", $p1Config,
        "--log-dir", $p1Logs,
        "--perf-output", (Join-Path $p1Root "perf_report.log")
    )
    $p2Args = $commonArgs + @(
        "--netplay-token", $p2Register.token,
        "--netplay-local-username", $p2Register.user.nick,
        "--netplay-user-id", "$($p2Register.user.id)",
        "--netplay-seat", "2",
        "--netplay-listen-port", "$P2NetplayListenPort",
        "--config-dir", $p2Config,
        "--log-dir", $p2Logs,
        "--perf-output", (Join-Path $p2Root "perf_report.log")
    )

    $routeMode = if ($ForceDirectLab.IsPresent) { "P2P direto forcado laboratorio" } elseif ($AllowP2P.IsPresent) { "P2P/relay automatico" } else { "relay forcado" }
    Write-Host "Abrindo duas instancias em modo $routeMode via servidor $(if ($PublicServer.IsPresent) { "publico" } else { "local" }) por $DurationSeconds segundos..."
    $p1Handle = Start-LoggedBackgroundProcess -FilePath $exe -Arguments $p1Args -WorkingDirectory $exeDir -StdoutPath (Join-Path $p1Root "stdout.log") -StderrPath (Join-Path $p1Root "stderr.log") -Environment $commonEnv
    Start-Sleep -Milliseconds 700
    $p2Handle = Start-LoggedBackgroundProcess -FilePath $exe -Arguments $p2Args -WorkingDirectory $exeDir -StdoutPath (Join-Path $p2Root "stdout.log") -StderrPath (Join-Path $p2Root "stderr.log") -Environment $commonEnv

    $deadline = (Get-Date).AddSeconds($DurationSeconds + 45)
    foreach ($handle in @($p1Handle, $p2Handle)) {
        while (-not $handle.Process.HasExited -and (Get-Date) -lt $deadline) {
            Start-Sleep -Milliseconds 250
        }
    }
    $p1NaturalExit = $p1Handle.Process.HasExited
    $p2NaturalExit = $p2Handle.Process.HasExited
    foreach ($handle in @($p1Handle, $p2Handle)) {
        if (-not $handle.Process.HasExited) {
            try { $handle.Process.Kill() } catch {}
        }
        try { [void]$handle.Process.WaitForExit(5000) } catch {}
        Save-ProcessOutput -Handle $handle
    }

    $serverTrace1 = Summarize-TraceFile -Path (Join-Path $p1Logs "server_lab_netplay_trace.log")
    $serverTrace2 = Summarize-TraceFile -Path (Join-Path $p2Logs "server_lab_netplay_trace.log")
    $liteTrace1 = Summarize-TraceFile -Path (Join-Path $p1Logs "netplay_lite_trace.log")
    $liteTrace2 = Summarize-TraceFile -Path (Join-Path $p2Logs "netplay_lite_trace.log")
    $ultraTrace1 = Summarize-TraceFile -Path (Join-Path $p1Logs "netplay_ultralight_trace.log")
    $ultraTrace2 = Summarize-TraceFile -Path (Join-Path $p2Logs "netplay_ultralight_trace.log")

    $summary = [System.Collections.Generic.List[string]]::new()
    $summary.Add("# ChampionsKOF relay netplay lab")
    $summary.Add("")
    $summary.Add(("- SessionId: {0}" -f $SessionId))
    $summary.Add(("- Driver: {0}" -f $Driver))
    $summary.Add(("- Exe: {0}" -f $exe))
    $summary.Add(("- Server mode: {0}" -f $(if ($PublicServer.IsPresent) { "public" } else { "local" })))
    $summary.Add(("- HTTP: {0}" -f $baseUrl))
    $summary.Add(("- Relay: {0}:{1}" -f $relayHostForClients, $relayPortForClients))
    $summary.Add(("- Route mode: {0}" -f $(if ($ForceDirectLab.IsPresent) { "direct-forced-lab" } elseif ($AllowP2P.IsPresent) { "auto-p2p-relay" } else { "relay-forced" })))
    $summary.Add(("- Simulated latency ms: {0}" -f $SimulatedLatencyMs))
    $summary.Add(("- Simulated jitter ms: {0}" -f $SimulatedJitterMs))
    $summary.Add(("- Simulated loss percent: {0}" -f $SimulatedLossPercent))
    $summary.Add(("- Client simulated latency ms: {0}" -f $ClientSimulatedLatencyMs))
    $summary.Add(("- Client simulated jitter ms: {0}" -f $ClientSimulatedJitterMs))
    $summary.Add(("- Client simulated loss percent: {0}" -f $ClientSimulatedLossPercent))
    $summary.Add(("- Scripted inputs: {0}" -f $ScriptedInputs.IsPresent))
    $summary.Add(("- Trace disabled: {0}" -f $NoTrace.IsPresent))
    $summary.Add(("- UltraLight trace: {0}" -f $UltraLightTrace.IsPresent))
    $summary.Add(("- Debug overlay disabled: {0}" -f $NoDebugOverlay.IsPresent))
    $summary.Add(("- Viewport backend: {0}" -f $(if ([string]::IsNullOrWhiteSpace($ViewportBackend)) { "auto" } else { $ViewportBackend.Trim() })))
    $summary.Add(("- Render filter: {0}" -f $RenderFilter))
    $summary.Add(("- Min input delay frames: {0}" -f $MinInputDelayFrames))
    $summary.Add(("- Max input delay frames: {0}" -f $MaxInputDelayFrames))
    $summary.Add(("- P1 netplay listen port: {0}" -f $P1NetplayListenPort))
    $summary.Add(("- P2 netplay listen port: {0}" -f $P2NetplayListenPort))
    $summary.Add(("- Room: {0}" -f $roomId))
    $summary.Add(("- Duration seconds: {0}" -f $DurationSeconds))
    $summary.Add(("- P1 exit: {0}" -f $p1Handle.Process.ExitCode))
    $summary.Add(("- P2 exit: {0}" -f $p2Handle.Process.ExitCode))
    $summary.Add(("- P1 natural exit: {0}" -f $p1NaturalExit))
    $summary.Add(("- P2 natural exit: {0}" -f $p2NaturalExit))
    $summary.Add("")
    $summary.Add("## Traces")
    $summary.Add("- P1 lite: exists=$($liteTrace1.Exists) lines=$($liteTrace1.Lines) mismatch=$($liteTrace1.MismatchLines) resync=$($liteTrace1.ResyncLines) fatal=$($liteTrace1.FatalLines)")
    $summary.Add("  progress P1 lite: maxFrame=$($liteTrace1.MaxFrame) activeLines=$($liteTrace1.ActiveFrameLines) runningStates=$($liteTrace1.RunningStateLines) waitingPeer=$($liteTrace1.WaitingPeerLines)")
    if ($liteTrace1.Exists) { $summary.Add("  runtime P1 lite: maxDelay=$($liteTrace1.MaxDelay) maxAdaptiveDelay=$($liteTrace1.MaxAdaptiveDelay) maxJitterBuffer=$($liteTrace1.MaxJitterBuffer)") }
    if (-not [string]::IsNullOrWhiteSpace($liteTrace1.FirstImportant)) { $summary.Add("  First important P1 lite: $($liteTrace1.FirstImportant)") }
    $summary.Add("- P2 lite: exists=$($liteTrace2.Exists) lines=$($liteTrace2.Lines) mismatch=$($liteTrace2.MismatchLines) resync=$($liteTrace2.ResyncLines) fatal=$($liteTrace2.FatalLines)")
    $summary.Add("  progress P2 lite: maxFrame=$($liteTrace2.MaxFrame) activeLines=$($liteTrace2.ActiveFrameLines) runningStates=$($liteTrace2.RunningStateLines) waitingPeer=$($liteTrace2.WaitingPeerLines)")
    if ($liteTrace2.Exists) { $summary.Add("  runtime P2 lite: maxDelay=$($liteTrace2.MaxDelay) maxAdaptiveDelay=$($liteTrace2.MaxAdaptiveDelay) maxJitterBuffer=$($liteTrace2.MaxJitterBuffer)") }
    if (-not [string]::IsNullOrWhiteSpace($liteTrace2.FirstImportant)) { $summary.Add("  First important P2 lite: $($liteTrace2.FirstImportant)") }
    $summary.Add("- P1 ultralight: exists=$($ultraTrace1.Exists) lines=$($ultraTrace1.Lines) mismatch=$($ultraTrace1.MismatchLines) resync=$($ultraTrace1.ResyncLines) fatal=$($ultraTrace1.FatalLines)")
    $summary.Add("  progress P1 ultralight: maxFrame=$($ultraTrace1.MaxFrame) activeLines=$($ultraTrace1.ActiveFrameLines) runningStates=$($ultraTrace1.RunningStateLines) waitingPeer=$($ultraTrace1.WaitingPeerLines)")
    if ($ultraTrace1.Exists) { $summary.Add("  runtime P1 ultralight: maxDelay=$($ultraTrace1.MaxDelay) maxAdaptiveDelay=$($ultraTrace1.MaxAdaptiveDelay) maxJitterBuffer=$($ultraTrace1.MaxJitterBuffer)") }
    if (-not [string]::IsNullOrWhiteSpace($ultraTrace1.FirstImportant)) { $summary.Add("  First important P1 ultralight: $($ultraTrace1.FirstImportant)") }
    $summary.Add("- P2 ultralight: exists=$($ultraTrace2.Exists) lines=$($ultraTrace2.Lines) mismatch=$($ultraTrace2.MismatchLines) resync=$($ultraTrace2.ResyncLines) fatal=$($ultraTrace2.FatalLines)")
    $summary.Add("  progress P2 ultralight: maxFrame=$($ultraTrace2.MaxFrame) activeLines=$($ultraTrace2.ActiveFrameLines) runningStates=$($ultraTrace2.RunningStateLines) waitingPeer=$($ultraTrace2.WaitingPeerLines)")
    if ($ultraTrace2.Exists) { $summary.Add("  runtime P2 ultralight: maxDelay=$($ultraTrace2.MaxDelay) maxAdaptiveDelay=$($ultraTrace2.MaxAdaptiveDelay) maxJitterBuffer=$($ultraTrace2.MaxJitterBuffer)") }
    if (-not [string]::IsNullOrWhiteSpace($ultraTrace2.FirstImportant)) { $summary.Add("  First important P2 ultralight: $($ultraTrace2.FirstImportant)") }
    $summary.Add("- P1 server lab: exists=$($serverTrace1.Exists) lines=$($serverTrace1.Lines) mismatch=$($serverTrace1.MismatchLines) resync=$($serverTrace1.ResyncLines) fatal=$($serverTrace1.FatalLines)")
    if (-not [string]::IsNullOrWhiteSpace($serverTrace1.FirstImportant)) { $summary.Add("  First important P1 server: $($serverTrace1.FirstImportant)") }
    $summary.Add("- P2 server lab: exists=$($serverTrace2.Exists) lines=$($serverTrace2.Lines) mismatch=$($serverTrace2.MismatchLines) resync=$($serverTrace2.ResyncLines) fatal=$($serverTrace2.FatalLines)")
    if (-not [string]::IsNullOrWhiteSpace($serverTrace2.FirstImportant)) { $summary.Add("  First important P2 server: $($serverTrace2.FirstImportant)") }
    $summary.Add("")
    $summary.Add("## Perf")
    foreach ($entry in @(@("P1", $p1Root), @("P2", $p2Root))) {
        $role = $entry[0]
        $perfPath = Join-Path $entry[1] "perf_report.log"
        $summary.Add("- $role stableFrameTime: $(Read-PerfLine -Path $perfPath -Prefix 'stableFrameTimeMs')")
        $summary.Add("- $role update_frame: $(Read-PerfLine -Path $perfPath -Prefix 'stableUpdateFrameMs' -FallbackPrefix 'update_frame')")
        $summary.Add("- $role render_submit: $(Read-PerfLine -Path $perfPath -Prefix 'stableRenderSubmitMs' -FallbackPrefix 'render_submit')")
        $summary.Add("- $role audio_pump: $(Read-PerfLine -Path $perfPath -Prefix 'audio_pump')")
        $summary.Add("- $role audioUnderrunCount: $(Read-PerfLine -Path $perfPath -Prefix 'audioUnderrunCount')")
    }
    $summary.Add("")
    $summary.Add("## Automated diagnosis")
    $diagnoses = @(
        (Get-PerfCauseDiagnosis -Role "P1" -RootPath $p1Root -LogsPath $p1Logs -TraceDisabled $NoTrace.IsPresent),
        (Get-PerfCauseDiagnosis -Role "P2" -RootPath $p2Root -LogsPath $p2Logs -TraceDisabled $NoTrace.IsPresent)
    )
    foreach ($diagnosis in $diagnoses) {
        $summary.Add(("- {0}: {1} | causa provavel: {2}" -f $diagnosis.Role, $diagnosis.Severity, $diagnosis.Tags))
        $summary.Add(("  frame p95={0} p99={1} max={2}; update p95={3} p99={4}; render p95={5}; audioUnderruns={6}" -f `
            (Format-NullableMs $diagnosis.FrameP95),
            (Format-NullableMs $diagnosis.FrameP99),
            (Format-NullableMs $diagnosis.FrameMax),
            (Format-NullableMs $diagnosis.UpdateP95),
            (Format-NullableMs $diagnosis.UpdateP99),
            (Format-NullableMs $diagnosis.RenderP95),
            $(if ($null -eq $diagnosis.AudioUnderruns) { "n/a" } else { $diagnosis.AudioUnderruns })))
        $summary.Add(("  scheduler p95={0}; timer jitter p95={1}; deadline miss p95={2}; netplay advance p95={3}; pump p95={4}; normal advance p95={5}; auth apply p95={6}; stableHitches={7}" -f `
            (Format-NullableMs $diagnosis.SchedulerP95),
            (Format-NullableMs $diagnosis.TimerJitterP95),
            (Format-NullableMs $diagnosis.DeadlineMissP95),
            (Format-NullableMs $diagnosis.NetplayAdvanceP95),
            (Format-NullableMs $diagnosis.NetplayPumpP95),
            (Format-NullableMs $diagnosis.NormalAdvanceP95),
            (Format-NullableMs $diagnosis.AuthApplyP95),
            $(if ($null -eq $diagnosis.StableHitches) { "n/a" } else { $diagnosis.StableHitches })))
        if ($diagnosis.SpikeCount -gt 0) {
            $summary.Add(("  spikes >=33ms: count={0}; maxWorst={1}; causas={2}" -f `
                $diagnosis.SpikeCount,
                (Format-NullableMs $diagnosis.SpikeMaxWorstMs),
                $(if ([string]::IsNullOrWhiteSpace($diagnosis.SpikeTopCauses)) { "n/a" } else { $diagnosis.SpikeTopCauses })))
        } else {
            $summary.Add("  spikes >=33ms: count=0")
        }
    }
    if ($NoTrace.IsPresent) {
        $summary.Add("- Observacao: trace desativado nesta rodada. Metrica de pacing e valida, mas prova fina de mismatch/resync precisa de rodada ultralight quando houver falha.")
    }
    $summary.Add("")
    $summary.Add("## Files")
    $summary.Add("- Server stdout: $(Join-Path $sessionRoot "server_stdout.log")")
    $summary.Add("- Server stderr: $(Join-Path $sessionRoot "server_stderr.log")")
    $summary.Add("- P1 logs: $p1Logs")
    $summary.Add("- P2 logs: $p2Logs")
    $summary.Add("")

    $primaryTrace1 = if ($ultraTrace1.Exists) { $ultraTrace1 } else { $liteTrace1 }
    $primaryTrace2 = if ($ultraTrace2.Exists) { $ultraTrace2 } else { $liteTrace2 }
    $minProgressFrame = [Math]::Min(300, [Math]::Max(60, [int]($DurationSeconds * 12)))
    $minActiveFrameLines = if ($UltraLightTrace.IsPresent) {
        [Math]::Max(3, [int][Math]::Floor($DurationSeconds * 0.45))
    } else {
        20
    }
    $insufficientProgress = -not $NoTrace.IsPresent -and (
        (-not $primaryTrace1.Exists) -or
        (-not $primaryTrace2.Exists) -or
        ($primaryTrace1.MaxFrame -lt $minProgressFrame) -or
        ($primaryTrace2.MaxFrame -lt $minProgressFrame) -or
        ($primaryTrace1.ActiveFrameLines -lt $minActiveFrameLines) -or
        ($primaryTrace2.ActiveFrameLines -lt $minActiveFrameLines)
    )
    if (-not $NoTrace.IsPresent) {
        $summary.Add("")
        $summary.Add("## Progress gate")
        $summary.Add("- Minimum expected frame: $minProgressFrame")
        $summary.Add("- Minimum active frame lines: $minActiveFrameLines")
        $summary.Add("- P1 primary trace maxFrame=$($primaryTrace1.MaxFrame) activeLines=$($primaryTrace1.ActiveFrameLines)")
        $summary.Add("- P2 primary trace maxFrame=$($primaryTrace2.MaxFrame) activeLines=$($primaryTrace2.ActiveFrameLines)")
    }

    $missingPerfRoles = @()
    foreach ($entry in @(@("P1", $p1Root), @("P2", $p2Root))) {
        $role = $entry[0]
        $perfPath = Join-Path $entry[1] "perf_report.log"
        $frameLine = Read-PerfLine -Path $perfPath -Prefix 'stableFrameTimeMs'
        $updateLine = Read-PerfLine -Path $perfPath -Prefix 'stableUpdateFrameMs' -FallbackPrefix 'update_frame'
        $renderLine = Read-PerfLine -Path $perfPath -Prefix 'stableRenderSubmitMs' -FallbackPrefix 'render_submit'
        if ([string]::IsNullOrWhiteSpace($frameLine) -or [string]::IsNullOrWhiteSpace($updateLine) -or [string]::IsNullOrWhiteSpace($renderLine)) {
            $missingPerfRoles += $role
        }
    }
    $missingPerf = $missingPerfRoles.Count -gt 0
    if ($missingPerf) {
        $summary.Add("")
        $summary.Add("## Perf gate")
        $summary.Add(("FAIL: metricas obrigatorias ausentes ou incompletas em {0}." -f ($missingPerfRoles -join ", ")))
    }

    $failed = ($p1NaturalExit -and $p1Handle.Process.ExitCode -ne 0) -or ($p2NaturalExit -and $p2Handle.Process.ExitCode -ne 0) `
        -or ($liteTrace1.MismatchLines + $liteTrace2.MismatchLines + $serverTrace1.MismatchLines + $serverTrace2.MismatchLines -gt 0) `
        -or ($ultraTrace1.MismatchLines + $ultraTrace2.MismatchLines -gt 0) `
        -or ($liteTrace1.FatalLines + $liteTrace2.FatalLines + $serverTrace1.FatalLines + $serverTrace2.FatalLines + $ultraTrace1.FatalLines + $ultraTrace2.FatalLines -gt 0) `
        -or $insufficientProgress `
        -or $missingPerf
    if ($failed) {
        $summary.Add("## Verdict")
        if ($missingPerf) {
            $summary.Add(("FAIL: a execucao via relay {0} nao gerou metricas obrigatorias nas duas instancias." -f $(if ($PublicServer.IsPresent) { "publico" } else { "local" })))
        } elseif ($insufficientProgress) {
            $summary.Add(("FAIL: a execucao via relay {0} nao gerou progresso real suficiente nas duas instancias." -f $(if ($PublicServer.IsPresent) { "publico" } else { "local" })))
        } else {
            $summary.Add(("FAIL: a execucao via relay {0} registrou falha, mismatch ou fatal." -f $(if ($PublicServer.IsPresent) { "publico" } else { "local" })))
        }
    } else {
        $summary.Add("## Verdict")
        $summary.Add(("OK inicial: duas instancias passaram pelo servidor/relay {0} sem mismatch/fatal no trace leve." -f $(if ($PublicServer.IsPresent) { "publico" } else { "local" })))
    }

    $summary -join [Environment]::NewLine | Set-Content -LiteralPath $summaryPath -Encoding UTF8
    Write-Host "Resumo: $summaryPath"
    Get-Content -LiteralPath $summaryPath

    if ($failed) {
        exit 1
    }
} finally {
    Stop-ProcessHandle -Handle $p1Handle
    Stop-ProcessHandle -Handle $p2Handle
    Stop-ProcessHandle -Handle $serverHandle
    if (-not [string]::IsNullOrWhiteSpace($endpointPath)) {
        if ($endpointHadExistingFile -and -not [string]::IsNullOrWhiteSpace($endpointBackupPath) -and (Test-Path -LiteralPath $endpointBackupPath)) {
            Copy-Item -LiteralPath $endpointBackupPath -Destination $endpointPath -Force
        } elseif (Test-Path -LiteralPath $endpointPath) {
            Remove-Item -LiteralPath $endpointPath -Force
        }
    }
}
