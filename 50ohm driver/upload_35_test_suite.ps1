# upload_35_test_suite.ps1
# Uploads all 6 OCEAN simulation jobs (35 test cases) to the Cadence server

$server = "user13@10.1.73.18"
$remote_dir = "~/validation/test_suite_35_6jobs"
$local_dir = Join-Path $PSScriptRoot "validation_generated\test_suite_35_6jobs"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " UPLOADING 35 TEST SUITE (6 JOBS) TO SERVER: $server" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Create remote directory
Write-Host "`n[1/3] Ensuring remote directory exists..." -ForegroundColor Yellow
ssh $server "mkdir -p $remote_dir"

# 2. Upload all files in test_suite_35_6jobs
Write-Host "`n[2/3] Uploading 6 OCEAN scripts, runners, and comparator..." -ForegroundColor Yellow
scp -r "$local_dir\*" "$server`:$remote_dir/"

# 3. Set executable permissions on server
Write-Host "`n[3/3] Setting execution permissions..." -ForegroundColor Yellow
ssh $server "chmod +x $remote_dir/*.sh $remote_dir/*.py"

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host " UPLOAD COMPLETE!" -ForegroundColor Green
Write-Host " Run on server with:" -ForegroundColor Cyan
Write-Host "   ssh $server" -ForegroundColor White
Write-Host "   cd $remote_dir" -ForegroundColor White
Write-Host "   ./run_all_6_jobs_parallel.sh" -ForegroundColor White
Write-Host "==========================================================" -ForegroundColor Green
