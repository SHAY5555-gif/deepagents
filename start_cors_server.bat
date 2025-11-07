@echo off
echo ===============================================
echo Starting LangGraph with CORS Support
echo ===============================================
echo.

REM Check if LangGraph is running
echo Checking if LangGraph is running on port 8123...
netstat -an | findstr :8123 >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: LangGraph does not appear to be running on port 8123
    echo Please run 'langgraph up' first in another terminal
    echo.
    pause
)

echo Starting CORS proxy server on port 8080...
python langgraph_server_with_cors.py

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Failed to start the server
    echo Make sure Python and dependencies are installed
    pause
)