# FilaFlow - PowerShell Launcher Unificado
$host.UI.RawUI.WindowTitle = "FilaFlow - Back + Front"
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "         FILAFLOW - INICIALIZADOR UNIFICADO (BACK + FRONT)            " -ForegroundColor Yellow
Write-Host "======================================================================" -ForegroundColor Cyan

$backDir = $PSScriptRoot
$frontDir = Resolve-Path "$backDir\..\FilaFlow"

# 1. Check Python Venv
if (!(Test-Path "$backDir\.venv\Scripts\python.exe")) {
    Write-Host "[1/4] Criando ambiente virtual Python..." -ForegroundColor Green
    python -m venv "$backDir\.venv"
    & "$backDir\.venv\Scripts\pip.exe" install -r "$backDir\requirements.txt"
} else {
    Write-Host "[1/4] Ambiente Python verificado (.venv)." -ForegroundColor Green
}

# 2. Start FastAPI Backend
Write-Host "[2/4] Iniciando Backend FastAPI (Porta 8000)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$backDir'; & '$backDir\.venv\Scripts\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

# 3. Start Vite Frontend
Write-Host "[3/4] Iniciando Frontend Vite (Porta 5174)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$frontDir'; npm run dev"

# 4. Wait and open browser
Start-Sleep -Seconds 3
Write-Host ""
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "     SISTEMAS INICIADOS COM SUCESSO!                                  " -ForegroundColor Green
Write-Host "  - Frontend:       http://localhost:5174/                            " -ForegroundColor White
Write-Host "  - Painel Empresa: http://localhost:5174/empresa/dashboard           " -ForegroundColor White
Write-Host "  - App Cliente:    http://localhost:5174/app                         " -ForegroundColor White
Write-Host "  - Backend API:    http://127.0.0.1:8000/                            " -ForegroundColor White
Write-Host "  - Swagger Docs:   http://127.0.0.1:8000/docs                        " -ForegroundColor White
Write-Host "======================================================================" -ForegroundColor Cyan

Start-Process "http://localhost:5174/"
