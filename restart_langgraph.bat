@echo off
echo ============================================
echo Restarting LangGraph Server
echo ============================================
echo.

echo Step 1: Stopping port 2024...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :2024 ^| findstr LISTENING') do (
    echo Killing process %%a
    taskkill /F /PID %%a 2>nul
)

echo.
echo Step 2: Waiting 3 seconds...
timeout /t 3 /nobreak >nul

echo.
echo Step 3: Starting LangGraph server...
cd /d "C:\projects\learn_ten_x_faster\deepagents"
start "" "C:\Users\yesha\AppData\Local\Programs\Python\Python311\Scripts\langgraph.exe" dev

echo.
echo ============================================
echo Server restart initiated!
echo Check the new window for server status.
echo ============================================
pause
