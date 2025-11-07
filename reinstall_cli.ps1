# Reinstall langgraph-cli
Write-Host "Removing langgraph.exe..." -ForegroundColor Yellow
Remove-Item "C:\Users\yesha\AppData\Local\Programs\Python\Python311\Scripts\langgraph.exe" -Force -ErrorAction SilentlyContinue

Write-Host "Installing langgraph-cli..." -ForegroundColor Yellow
pip install --force-reinstall langgraph-cli

Write-Host "Done!" -ForegroundColor Green
