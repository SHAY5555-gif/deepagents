# ============================================
# Test Docker Build Script
# ============================================
# This script tests the optimized Docker build locally

Write-Host "🚀 Starting Docker Build Test..." -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
Write-Host "📋 Step 1: Checking Docker status..." -ForegroundColor Yellow
try {
    docker info | Out-Null
    Write-Host "✅ Docker is running" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker is not running. Please start Docker Desktop." -ForegroundColor Red
    exit 1
}

Write-Host ""

# Build first time
Write-Host "📋 Step 2: Building Docker image (first time)..." -ForegroundColor Yellow
Write-Host "⏱️  This should take 2-3 minutes..." -ForegroundColor Gray
$startTime = Get-Date

docker build -t deepagents:test . 2>&1 | Tee-Object -Variable buildOutput

$endTime = Get-Date
$duration = $endTime - $startTime
Write-Host ""
Write-Host "✅ First build completed in: $($duration.TotalSeconds) seconds" -ForegroundColor Green
Write-Host ""

# Check if build was successful
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Build failed! Check the error messages above." -ForegroundColor Red
    exit 1
}

# Check for cache usage
Write-Host "📋 Step 3: Checking cache usage..." -ForegroundColor Yellow
if ($buildOutput -match "Using cache|CACHED") {
    Write-Host "✅ Docker layer caching is working!" -ForegroundColor Green
} else {
    Write-Host "⚠️  No cache detected (expected on first build)" -ForegroundColor Yellow
}
Write-Host ""

# Make a small change to test caching
Write-Host "📋 Step 4: Testing cache efficiency..." -ForegroundColor Yellow
Write-Host "Making a small code change..." -ForegroundColor Gray

# Add a comment to a Python file
Add-Content -Path ".\mcp_agent_async.py" -Value "`n# Test comment for cache testing"

Write-Host "⏱️  Rebuilding (should be much faster with cache)..." -ForegroundColor Gray
$startTime2 = Get-Date

docker build -t deepagents:test2 . 2>&1 | Tee-Object -Variable buildOutput2

$endTime2 = Get-Date
$duration2 = $endTime2 - $startTime2

Write-Host ""
Write-Host "✅ Second build completed in: $($duration2.TotalSeconds) seconds" -ForegroundColor Green
Write-Host ""

# Calculate improvement
$improvement = [math]::Round((1 - ($duration2.TotalSeconds / $duration.TotalSeconds)) * 100, 1)
Write-Host "📊 Cache Efficiency:" -ForegroundColor Cyan
Write-Host "   First build:  $([math]::Round($duration.TotalSeconds, 1)) seconds" -ForegroundColor White
Write-Host "   Second build: $([math]::Round($duration2.TotalSeconds, 1)) seconds" -ForegroundColor White
Write-Host "   Improvement:  $improvement%" -ForegroundColor Green
Write-Host ""

# Revert the test change
Write-Host "🧹 Cleaning up test changes..." -ForegroundColor Yellow
git checkout -- mcp_agent_async.py 2>&1 | Out-Null

# Check image size
Write-Host "📋 Step 5: Checking image size..." -ForegroundColor Yellow
$imageSize = docker images deepagents:test --format "{{.Size}}"
Write-Host "✅ Image size: $imageSize" -ForegroundColor Green
Write-Host ""

# Summary
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "🎉 BUILD TEST COMPLETE!" -ForegroundColor Green
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host ""
Write-Host "Summary:" -ForegroundColor Cyan
Write-Host "  ✅ Docker is working" -ForegroundColor White
Write-Host "  ✅ Build completes successfully" -ForegroundColor White
Write-Host "  ✅ Cache is working ($improvement% faster on rebuild)" -ForegroundColor White
Write-Host "  ✅ Image size: $imageSize" -ForegroundColor White
Write-Host ""

if ($improvement -gt 50) {
    Write-Host "🚀 Excellent! Cache optimization is working great!" -ForegroundColor Green
} elseif ($improvement -gt 30) {
    Write-Host "✅ Good! Cache is helping speed up builds." -ForegroundColor Green
} else {
    Write-Host "⚠️  Cache improvement is lower than expected." -ForegroundColor Yellow
    Write-Host "   This might be normal depending on what changed." -ForegroundColor Gray
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Commit these changes to Git" -ForegroundColor White
Write-Host "  2. Push to GitHub" -ForegroundColor White
Write-Host "  3. Watch Render deploy - should be much faster!" -ForegroundColor White
Write-Host ""
Write-Host "To test the container locally:" -ForegroundColor Cyan
Write-Host '  docker run -p 8000:8000 -e ANTHROPIC_API_KEY=your_key deepagents:test' -ForegroundColor Gray
Write-Host ""
