@echo off
echo Killing all LangGraph processes...

REM Kill all python processes
for /f "tokens=2" %%i in ('tasklist ^| findstr python.exe') do taskkill /F /PID %%i 2>nul

REM Kill all langgraph.exe processes
for /f "tokens=2" %%i in ('tasklist ^| findstr langgraph.exe') do taskkill /F /PID %%i 2>nul

echo.
echo Waiting 3 seconds...
timeout /t 3 /nobreak >nul

echo.
echo Starting LangGraph Studio server...
echo.

cd /d C:\projects\learn_ten_x_faster\deepagents

C:\Users\yesha\AppData\Local\Programs\Python\Python311\Scripts\langgraph.exe dev

pause
