# stop_aquanova.ps1
# (Clean Shutdown Script)

param(
  [switch]$StopRedis = $false  # Redis 컨테이너까지 끄려면 -StopRedis 옵션 사용
)

$ErrorActionPreference = "SilentlyContinue" # 이미 죽은 프로세스 에러 무시
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# -------------------------------------------------------------
# 1. 경로 설정 (run 스크립트와 동일)
# -------------------------------------------------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$DataDir = Join-Path $ScriptDir ".data"
$PidFile = Join-Path $DataDir "pids.json"

Write-Host "=============================================" -ForegroundColor Magenta
Write-Host "      AquaNova Stopper (Cleanup)" -ForegroundColor Magenta
Write-Host "=============================================" -ForegroundColor Magenta

# -------------------------------------------------------------
# 2. PID 파일 확인 및 프로세스 종료
# -------------------------------------------------------------
if (Test-Path $PidFile) {
    Write-Host "[1/3] Reading PIDs from $PidFile..."
    
    try {
        $JsonContent = Get-Content -Path $PidFile -Raw -Encoding UTF8
        $PidData = $JsonContent | ConvertFrom-Json
        
        # 종료 대상 목록 정의 (API -> Worker -> UI 순서 권장)
        $Targets = @(
            @{ Name="API";    Pid=$PidData.api.pid },
            @{ Name="Worker"; Pid=$PidData.worker.pid },
            @{ Name="UI";     Pid=$PidData.ui.pid }
        )

        foreach ($t in $Targets) {
            if ($t.Pid) {
                Write-Host "  - Killing $($t.Name) (PID: $($t.Pid))..." -NoNewline
                
                # [핵심] taskkill /F(강제) /T(트리:자식포함) 사용
                # Stop-Process는 cmd로 실행된 자식 프로세스(python, node)를 놓칠 수 있음
                $proc = Get-Process -Id $t.Pid -ErrorAction SilentlyContinue
                
                if ($proc) {
                    # 윈도우 네이티브 명령어로 프로세스 트리 전체 사살
                    cmd /c "taskkill /F /T /PID $($t.Pid) > NUL 2>&1"
                    Write-Host " [Done]" -ForegroundColor Green
                } else {
                    Write-Host " [Already Dead]" -ForegroundColor DarkGray
                }
            }
        }
    } catch {
        Write-Host "  [ERROR] Failed to parse pids.json or kill processes." -ForegroundColor Red
    }

    # -------------------------------------------------------------
    # 3. PID 파일 정리
    # -------------------------------------------------------------
    Write-Host "[2/3] Cleaning up PID file..."
    Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
    Write-Host "  - $PidFile deleted." -ForegroundColor Gray

} else {
    Write-Host "[WARN] No pids.json found. Assuming services are stopped." -ForegroundColor Yellow
}

# -------------------------------------------------------------
# 4. Redis 종료 (옵션)
# -------------------------------------------------------------
if ($StopRedis) {
    Write-Host "[3/3] Stopping Redis container..."
    docker stop aquanova-redis 2>$null
    Write-Host "  - Redis stopped." -ForegroundColor Yellow
} else {
    Write-Host "[3/3] Skipping Redis stop (Use -StopRedis to force stop)." -ForegroundColor Gray
}

Write-Host "`nAquaNova Services have been terminated." -ForegroundColor Magenta