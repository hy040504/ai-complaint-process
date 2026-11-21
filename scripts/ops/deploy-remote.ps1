<#
.SYNOPSIS
  지정한 브랜치(기본 main)의 추적 파일을 SSH 서버에 올리고 서비스를 재시작합니다.

.DESCRIPTION
  Git 원격 저장소를 거치지 않고 `git archive`로 만든 tar를 SSH 표준입력으로 전송합니다.
  접속 정보는 저장소에 두지 않고, 사용자가 가진 접속용 배치 파일(`navy2025-ssh.bat` 형식)에서
  `SSH_USER`·`TAILCAT_ADDR`만 읽어 Tailcat 경유 SSH로 접속합니다. 주소는 화면에 출력하지 않습니다.

  서버 쪽 처리:
    1. 이전 배포 목록(`.deploy-manifest`)의 파일만 지워 옛 경로가 남지 않게 합니다.
       `.venv*`·`.rag-*`·`.web-data`·`.env`·`rag/origin/dumps`는 건드리지 않습니다.
    2. tar를 풀고 새 목록과 배포 커밋(`.deploy-rev`)을 기록합니다.
    3. 사용자 서비스(`cheongju-rag`·`cheongju-web`·`cheongju-lab`)를 재시작하고 헬스를 확인합니다.

.PARAMETER Branch
  배포할 브랜치입니다. 기본값은 main입니다.
.PARAMETER SshBat
  접속용 배치 파일 경로입니다. 기본값은 바탕화면의 navy2025-ssh.bat입니다.
.PARAMETER RemoteDir
  서버의 프로젝트 경로입니다. 기본값은 ~/ai-complaint-process입니다.
.PARAMETER SkipRestart
  파일만 올리고 서비스는 재시작하지 않습니다.
.EXAMPLE
  powershell -File scripts/ops/deploy-remote.ps1
#>
param(
    [string]$Branch = "main",
    [string]$SshBat = (Join-Path $env:USERPROFILE "Desktop\navy2025-ssh.bat"),
    [string]$RemoteDir = "~/ai-complaint-process",
    [switch]$SkipRestart
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $root

if (-not (Test-Path $SshBat)) { throw "접속용 배치 파일을 찾을 수 없습니다: $SshBat" }
$bat = Get-Content $SshBat -Raw -Encoding utf8
$sshUser = [regex]::Match($bat, 'set "SSH_USER=([^"]+)"').Groups[1].Value
$addr = [regex]::Match($bat, 'set "TAILCAT_ADDR=([^"]+)"').Groups[1].Value
if (-not $sshUser -or -not $addr) { throw "배치 파일에서 SSH_USER·TAILCAT_ADDR를 읽지 못했습니다." }
$tailcat = Join-Path $env:USERPROFILE ".local\bin\tailcat.exe"
if (-not (Test-Path $tailcat)) { $tailcat = "tailcat" }
$gitSsh = @("$env:LOCALAPPDATA\Programs\Git\usr\bin", "$env:ProgramFiles\Git\usr\bin") |
    Where-Object { Test-Path (Join-Path $_ "ssh.exe") } | Select-Object -First 1
if ($gitSsh) { $env:PATH = "$gitSsh;$env:USERPROFILE\.local\bin;$env:PATH" }

# 배포 대상 브랜치와 작업 트리 상태 확인
git rev-parse --verify --quiet $Branch | Out-Null
if ($LASTEXITCODE -ne 0) { throw "브랜치가 없습니다: $Branch" }
$rev = (git rev-parse --short $Branch).Trim()
$subject = (git log -1 --format=%s $Branch).Trim()
$current = (git branch --show-current).Trim()
if ($current -ne $Branch) { Write-Warning "현재 브랜치($current)와 배포 브랜치($Branch)가 다릅니다. $Branch 의 커밋을 올립니다." }
if (git status --porcelain --untracked-files=no) { Write-Warning "커밋하지 않은 변경은 배포에 포함되지 않습니다." }
Write-Host "배포 대상: $Branch @ $rev  $subject"

$tmp = Join-Path $env:TEMP "acp-deploy-$rev"
if ([string]::IsNullOrWhiteSpace($tmp) -or $tmp.Length -lt 10) { throw "임시 경로를 만들지 못했습니다." }
New-Item -ItemType Directory -Force $tmp | Out-Null
$tar = Join-Path $tmp "release.tar"
git archive --format=tar -o $tar $Branch
git ls-tree -r --name-only $Branch | Set-Content -Encoding utf8 (Join-Path $tmp "manifest.txt")

function Invoke-Remote {
    # 원격에서 bash 스크립트를 실행합니다. 두 번째 인자가 있으면 스크립트 대신 그 명령을 실행하고
    # 파일 내용을 표준입력으로 보냅니다(바이너리 안전: 파일 리다이렉트).
    param([string]$Script, [string]$StdinFile)
    $local = Join-Path $tmp ("remote-" + [guid]::NewGuid().ToString("N") + ".sh")
    [IO.File]::WriteAllText($local, ($Script -replace "`r", ""), (New-Object Text.UTF8Encoding($false)))
    $stdout = "$local.out"
    $stderr = "$local.err"
    if ($StdinFile) { $in = $StdinFile; $cmd = $Script } else { $in = $local; $cmd = "bash -s" }
    $p = Start-Process -FilePath $tailcat -ArgumentList @("ssh", "$sshUser@$addr", ('"' + $cmd + '"')) `
        -RedirectStandardInput $in -RedirectStandardOutput $stdout -RedirectStandardError $stderr -NoNewWindow -Wait -PassThru
    if (Test-Path $stdout) { Get-Content $stdout -Encoding utf8 }
    if ($p.ExitCode -ne 0) {
        if (Test-Path $stderr) { Get-Content $stderr -Encoding utf8 | Select-Object -Last 8 }
        throw "원격 명령 실패(exit=$($p.ExitCode))"
    }
}

# 1) 이전 배포 파일 정리
$cleanup = Get-Content (Join-Path $PSScriptRoot "remote\cleanup.sh") -Raw -Encoding utf8
Invoke-Remote ($cleanup.Replace("__DIR__", $RemoteDir)) $null

# 2) tar 전송·해제
Invoke-Remote "cd $RemoteDir && tar -xf - && echo extracted" $tar

# 3) 배포 목록·리비전 기록, 실행 권한
Invoke-Remote "cat > $RemoteDir/.deploy-manifest" (Join-Path $tmp "manifest.txt")
$finish = Get-Content (Join-Path $PSScriptRoot "remote\finish.sh") -Raw -Encoding utf8
Invoke-Remote ($finish.Replace("__DIR__", $RemoteDir).Replace("__BRANCH__", $Branch).Replace("__REV__", $rev)) $null

# 4) 서비스 재시작과 헬스 확인
if (-not $SkipRestart) {
    $restart = Get-Content (Join-Path $PSScriptRoot "remote\restart.sh") -Raw -Encoding utf8
    Invoke-Remote $restart $null
}

if ($tmp -like "*acp-deploy-*") { Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue }
Write-Host "배포 완료: $Branch@$rev"
