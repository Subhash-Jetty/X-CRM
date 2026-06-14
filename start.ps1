Write-Host "=========================================="
Write-Host "       Starting XENO AI-Native CRM        "
Write-Host "=========================================="
Write-Host ""

$root = $PSScriptRoot
$venvPath = Join-Path $root "venv"
$pythonExe = Join-Path $venvPath "Scripts\python.exe"

function Test-Venv {
    param([string]$PythonPath)
    return Test-Python312 $PythonPath
}

function Test-Python312 {
    param([string]$PythonPath)
    if (-Not (Test-Path $PythonPath)) {
        return $false
    }
    & $PythonPath -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)" *> $null
    return $LASTEXITCODE -eq 0
}

function Find-Python312 {
    $localTestPython = Join-Path $root ".test-venv\Scripts\python.exe"
    if (Test-Python312 $localTestPython) {
        return $localTestPython
    }

    $codexBundledPython = Join-Path $HOME ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-Python312 $codexBundledPython) {
        return $codexBundledPython
    }

    $python312 = Get-Command python3.12 -ErrorAction SilentlyContinue
    if ($python312 -and (Test-Python312 $python312.Source)) {
        return $python312.Source
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python -and (Test-Python312 $python.Source)) {
        return $python.Source
    }

    return $null
}

function Normalize-ProcessPathEnvironment {
    $processPath = [Environment]::GetEnvironmentVariable("Path", "Process")
    if ([string]::IsNullOrWhiteSpace($processPath)) {
        $processPath = [Environment]::GetEnvironmentVariable("PATH", "Process")
    }

    if (-Not [string]::IsNullOrWhiteSpace($processPath)) {
        [Environment]::SetEnvironmentVariable("PATH", $null, "Process")
        [Environment]::SetEnvironmentVariable("Path", $null, "Process")
        [Environment]::SetEnvironmentVariable("Path", $processPath, "Process")
        $env:Path = $processPath
    }
}

function Stop-UvicornListener {
    param(
        [int]$Port,
        [string]$ServiceName
    )

    $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($listener in $listeners) {
        $processId = $listener.OwningProcess
        $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
        $commandLine = if ($processInfo) { $processInfo.CommandLine } else { "" }

        if ($commandLine -match "uvicorn") {
            Write-Host "-> Stopping existing $ServiceName listener on port $Port (PID $processId)..."
            Stop-Process -Id $processId -Force
            Start-Sleep -Seconds 1
        } else {
            throw "Port $Port is already in use by PID $processId. Stop that process and rerun start.ps1."
        }
    }
}

Normalize-ProcessPathEnvironment

# Create or repair the virtual environment.
if (-Not (Test-Venv $pythonExe)) {
    Write-Host "-> Creating Python Virtual Environment..."
    if (Test-Path $venvPath) {
        Remove-Item -LiteralPath $venvPath -Recurse -Force
    }

    $py312 = Get-Command py -ErrorAction SilentlyContinue
    if ($py312) {
        py -3.12 -m venv $venvPath
    }

    if ($LASTEXITCODE -ne 0 -or -Not (Test-Venv $pythonExe)) {
        $python312Exe = Find-Python312
        if ($python312Exe) {
            & $python312Exe -m venv $venvPath
        }
    }

    if (-Not (Test-Venv $pythonExe)) {
        throw "Python 3.12 is required because backend native dependencies are pinned for 3.12. Install Python 3.12 and rerun start.ps1."
    }
}

# Activate venv
Write-Host "-> Activating venv and installing dependencies..."
.\venv\Scripts\Activate.ps1
& $pythonExe -m pip install -r backend/requirements.txt
& $pythonExe -m pip install -r channel-service/requirements.txt

# Run Data Ingestion if needed
Write-Host "-> Ingesting BeanBox Seed Data..."
& $pythonExe (Join-Path $root "seed\ingest.py")

# Clear stale background servers so code changes load after a restart.
Stop-UvicornListener -Port 8001 -ServiceName "Channel Service"
Stop-UvicornListener -Port 8000 -ServiceName "Backend API"

# Start Channel Service (Background)
Write-Host "-> Starting Channel Service on port 8001..."
Start-Process -WindowStyle Hidden -FilePath $pythonExe -ArgumentList "-m uvicorn app.main:app --host 0.0.0.0 --port 8001" -WorkingDirectory (Join-Path $root "channel-service")
Start-Sleep -Seconds 2

# Start Backend API (Background)
Write-Host "-> Starting Backend API on port 8000..."
Start-Process -WindowStyle Hidden -FilePath $pythonExe -ArgumentList "-m uvicorn app.main:app --host 0.0.0.0 --port 8000" -WorkingDirectory (Join-Path $root "backend")
Start-Sleep -Seconds 2

# Start Frontend (Interactive)
Write-Host "-> Starting Next.js Frontend on port 3000..."
Set-Location (Join-Path $root "frontend")
npm run dev
