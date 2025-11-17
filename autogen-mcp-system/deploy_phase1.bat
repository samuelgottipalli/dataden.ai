@echo off
REM Phase 1 Deployment Script for Windows
REM Quick deployment of interactive agent features

echo ==========================================
echo Phase 1: Interactive Agents - Deployment
echo ==========================================
echo.

REM Check if we're in the right directory
if not exist "mcp_server\main.py" (
    echo Error: Not in autogen-mcp-system directory
    echo Please run this script from the project root
    exit /b 1
)

REM Step 1: Backup existing files
echo Step 1: Backing up current files...
if exist "agents\enhanced_orchestrator.py" (
    for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c%%a%%b)
    for /f "tokens=1-2 delims=/:" %%a in ('time /t') do (set mytime=%%a%%b)
    copy agents\enhanced_orchestrator.py agents\enhanced_orchestrator_backup_%mydate%_%mytime%.py >nul
    echo [OK] Backed up orchestrator
)

if exist "mcp_server\api_routes.py" (
    for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c%%a%%b)
    for /f "tokens=1-2 delims=/:" %%a in ('time /t') do (set mytime=%%a%%b)
    copy mcp_server\api_routes.py mcp_server\api_routes_backup_%mydate%_%mytime%.py >nul
    echo [OK] Backed up API routes
)

REM Step 2: Deploy new files
echo.
echo Step 2: Deploying Phase 1 files...

REM Check if phase1 files exist
if not exist "phase1_enhanced_orchestrator.py" (
    echo Error: phase1_enhanced_orchestrator.py not found
    echo Please ensure you've downloaded the Phase 1 files
    exit /b 1
)

if not exist "phase1_api_routes.py" (
    echo Error: phase1_api_routes.py not found
    echo Please ensure you've downloaded the Phase 1 files
    exit /b 1
)

REM Copy files
copy phase1_enhanced_orchestrator.py agents\enhanced_orchestrator.py >nul
echo [OK] Deployed orchestrator

copy phase1_api_routes.py mcp_server\api_routes.py >nul
echo [OK] Deployed API routes

REM Step 3: Test syntax
echo.
echo Step 3: Testing Python syntax...

python -m py_compile agents\enhanced_orchestrator.py 2>nul
if %errorlevel% equ 0 (
    echo [OK] Orchestrator syntax OK
) else (
    echo [ERROR] Orchestrator syntax error
    exit /b 1
)

python -m py_compile mcp_server\api_routes.py 2>nul
if %errorlevel% equ 0 (
    echo [OK] API routes syntax OK
) else (
    echo [ERROR] API routes syntax error
    exit /b 1
)

REM Step 4: Test imports
echo.
echo Step 4: Testing imports...

python -c "from agents.enhanced_orchestrator import EnhancedAgentOrchestrator" 2>nul
if %errorlevel% equ 0 (
    echo [OK] Orchestrator imports OK
) else (
    echo [ERROR] Orchestrator import error
    echo Run: python -c "from agents.enhanced_orchestrator import EnhancedAgentOrchestrator"
    exit /b 1
)

python -c "from mcp_server.api_routes import router" 2>nul
if %errorlevel% equ 0 (
    echo [OK] API routes imports OK
) else (
    echo [ERROR] API routes import error
    echo Run: python -c "from mcp_server.api_routes import router"
    exit /b 1
)

REM Step 5: Summary
echo.
echo ==========================================
echo [SUCCESS] Phase 1 Deployment Complete!
echo ==========================================
echo.
echo Next steps:
echo 1. Test locally: python agents\enhanced_orchestrator.py
echo 2. Start server: python mcp_server\main.py
echo 3. Test API: curl http://localhost:8000/api/v1/health
echo.
echo Documentation: PHASE1_IMPLEMENTATION_GUIDE.md
echo.

pause
