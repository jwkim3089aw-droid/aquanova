# run_aquanova.ps1
# (NSSM Service Version - Enhanced Process Management)

param(
  [int]$ApiPort = 8003,
  [string]$ApiHost = "127.0.0.1", 
  [string]$RedisContainer = "aquanova-redis",
  [string]$RedisUrl = "redis://localhost:6379/0"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# -------------------------------------------------------------
# [Helper] 프로세스 트리 강제 종료 함수
# -------------------------------------------------------------
function Stop-ProcessTree {
    param([int]$TargetPid, [string]$Name)
    if (!$TargetPid) { return }

    try {
        $proc = Get-Process -Id $TargetPid -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "   [KILL] Stopping $Name (PID: $TargetPid) and its children..." -ForegroundColor Yellow
            # /F: 강제종료, /T: 자식 프로세스까지 트리 종료 (핵심!)
            taskkill.exe /F /PID $TargetPid /T | Out-Null
        }
    } catch {
        Write-Host "   [INFO] Process $Name ($TargetPid) already gone." -ForegroundColor Gray
    }
}

# -------------------------------------------------------------
# 1. 경로 및 환경 설정
# -------------------------------------------------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "   AquaNova Launcher (Safe Service Mode)" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# venv 확인
$VenvPython = Join-Path $ScriptDir ".venv\Scripts\python.exe"
if (!(Test-Path $VenvPython)) {
    Write-Error "[ERROR] .venv 폴더나 python.exe가 없습니다: $VenvPython"
    exit 1
}

# 폴더 경로 정의
$LogDir  = Join-Path $ScriptDir ".logs"
$DataDir = Join-Path $ScriptDir ".data"
$PidFile = Join-Path $DataDir "pids.json"

# 필요한 폴더 생성 (초기 확인용)
@($LogDir, $DataDir, "$ScriptDir\.assets\fonts", "$ScriptDir\reports\outputs") | ForEach-Object {
    if (!(Test-Path $_)) { New-Item -ItemType Directory -Path $_ -Force | Out-Null }
}

# 환경 변수 설정
$env:AQUANOVA_FONT_PATH = Join-Path $ScriptDir ".assets\fonts\NotoSans-Variable.ttf"
$env:FONT_PATH = $env:AQUANOVA_FONT_PATH
$env:REDIS_URL = $RedisUrl
$env:PYTHONPATH = $ScriptDir
$env:PYTHONUTF8 = "1"

# -------------------------------------------------------------
# 2. [중요] 기존 좀비 프로세스 청소 (Clean Start)
# -------------------------------------------------------------
Write-Host "[1/6] Cleaning up previous sessions..."
if (Test-Path $PidFile) {
    try {
        $OldStatus = Get-Content $PidFile -Raw | ConvertFrom-Json
        if ($OldStatus) {
            if ($OldStatus.api.pid) { Stop-ProcessTree -TargetPid $OldStatus.api.pid -Name "Old API" }
            if ($OldStatus.worker.pid) { Stop-ProcessTree -TargetPid $OldStatus.worker.pid -Name "Old Worker" }
            if ($OldStatus.ui.pid) { Stop-ProcessTree -TargetPid $OldStatus.ui.pid -Name "Old UI" }
        }
    } catch {
        Write-Host "   [WARN] Failed to read old PID file. Skipping cleanup." -ForegroundColor Yellow
    }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

# ▼▼▼▼▼▼▼▼▼▼ [추가됨] 로그 폴더 초기화 ▼▼▼▼▼▼▼▼▼▼
# 프로세스가 죽은 뒤라야 파일 잠금이 풀려서 삭제 가능
if (Test-Path $LogDir) {
    Write-Host "   [CLEAN] Wiping logs folder: $LogDir" -ForegroundColor Yellow
    try {
        Remove-Item -Path $LogDir -Recurse -Force -ErrorAction Stop
    } catch {
        Write-Host "   [WARN] Could not delete some log files (File in use?). Continuing..." -ForegroundColor DarkGray
    }
}
# 폴더 다시 생성 (안 만들면 로깅 에러 남)
if (!(Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
# ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲

# -------------------------------------------------------------
# 3. Redis 확인
# -------------------------------------------------------------
Write-Host "[2/6] Checking Redis..."
try {
    $null = docker info 2>&1
    if ($LASTEXITCODE -eq 0) {
        $state = docker inspect -f '{{.State.Running}}' $RedisContainer 2>$null
        if ($state -ne "true") {
            Write-Host "   - Starting Redis container..."
            docker start $RedisContainer 2>$null | Out-Null
        }
    }
} catch {
    Write-Host "   [WARN] Redis check skipped (Docker issue)." -ForegroundColor Yellow
}

# -------------------------------------------------------------
# 4. 프로세스 실행
# -------------------------------------------------------------
Write-Host "[3/6] Launching processes..."
$ApiLog = Join-Path $LogDir "api.log"
$WkrLog = Join-Path $LogDir "worker.log"
$UiLog  = Join-Path $LogDir "ui.log"

# (1) API 실행
Write-Host "   - Starting API ($ApiHost`:$ApiPort)..." 
$ApiCmd = "call ""$VenvPython"" -m uvicorn app.main:app --host $ApiHost --port $ApiPort --reload"
$ApiProc = Start-Process -FilePath "cmd.exe" -ArgumentList "/c $ApiCmd > ""$ApiLog"" 2>&1" -WorkingDirectory $ScriptDir -WindowStyle Hidden -PassThru
$ApiPid = $ApiProc.Id

# (2) Worker 실행
Write-Host "   - Starting Worker..."
$WkrCmd = "call ""$VenvPython"" -m app.workers.report_worker"
$WkrProc = Start-Process -FilePath "cmd.exe" -ArgumentList "/c $WkrCmd > ""$WkrLog"" 2>&1" -WorkingDirectory $ScriptDir -WindowStyle Hidden -PassThru
$WkrPid = $WkrProc.Id

# (3) UI 실행
$UiDir = Join-Path $ScriptDir "ui"
$UiPid = 0
if (Test-Path $UiDir) {
    Write-Host "   - Starting UI..."
    $UiCmd = "npx vite --port 5174 --host 127.0.0.1"
    $UiProc = Start-Process -FilePath "cmd.exe" -ArgumentList "/c $UiCmd > ""$UiLog"" 2>&1" -WorkingDirectory $UiDir -WindowStyle Hidden -PassThru
    $UiPid = $UiProc.Id
}

# -------------------------------------------------------------
# 5. PID 저장
# -------------------------------------------------------------
Write-Host "[4/6] Saving PID info..."
$StatusData = @{
    api = @{ pid = $ApiPid }
    worker = @{ pid = $WkrPid }
    ui = @{ pid = $UiPid }
    started = (Get-Date).ToString("s")
}
$StatusData | ConvertTo-Json | Set-Content -Encoding UTF8 -Path $PidFile

# -------------------------------------------------------------
# 6. 헬스 체크
# -------------------------------------------------------------
Write-Host "[5/6] Health Check (Waiting 5s)..."
Start-Sleep -Seconds 5
try {
    $resp = Invoke-WebRequest "http://$ApiHost`:$ApiPort/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
    if ($resp.StatusCode -eq 200) { Write-Host "   [OK] API is ALIVE." -ForegroundColor Green }
} catch { Write-Host "   [INFO] API booting..." -ForegroundColor Gray }

# -------------------------------------------------------------
# 7. 서비스 모니터링 루프 (메인 로직)
# -------------------------------------------------------------
Write-Host "`n[6/6] Service Running. Monitoring PIDs: API[$ApiPid], Worker[$WkrPid]..." -ForegroundColor Cyan

try {
    while ($true) {
        if ($ApiProc.HasExited) {
            Write-Error "CRITICAL: API Process terminated unexpectedly."
            break 
        }
        if ($WkrProc.HasExited) {
            Write-Error "CRITICAL: Worker Process terminated unexpectedly."
            break
        }
        Start-Sleep -Seconds 3
    }
}
finally {
    # ---------------------------------------------------------
    # [종료 처리] NSSM이 Stop/Restart 보낼 때 실행됨
    # ---------------------------------------------------------
    Write-Host "`n[STOP] Shutting down service and cleaning up children..." -ForegroundColor Yellow
    
    Stop-ProcessTree -TargetPid $ApiPid -Name "API"
    Stop-ProcessTree -TargetPid $WkrPid -Name "Worker"
    if ($UiPid -gt 0) { Stop-ProcessTree -TargetPid $UiPid -Name "UI" }
    
    if (Test-Path $PidFile) { Remove-Item $PidFile -Force }
    Write-Host "[STOP] Cleanup complete." -ForegroundColor Green
}