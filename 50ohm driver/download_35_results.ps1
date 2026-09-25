# download_35_results.ps1
# Downloads simulation results of the 35 test cases from server to local PC

$server = "user13@10.1.73.18"
$remote_dir = "~/validation/test_suite_35_6jobs"
$local_dir = Join-Path $PSScriptRoot "validation_generated\test_suite_35_6jobs"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " DOWNLOADING 35 TEST SUITE RESULTS FROM SERVER: $server" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Download result CSVs
Write-Host "`n[1/2] Downloading result CSVs..." -ForegroundColor Yellow
scp "$server`:$remote_dir/results_job*.csv" "$local_dir\"

# 2. Download simulation logs
Write-Host "`n[2/2] Downloading log files..." -ForegroundColor Yellow
scp -r "$server`:$remote_dir/logs_6jobs" "$local_dir\"

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host " DOWNLOAD COMPLETE! Running local evaluation..." -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green

python "$local_dir\compare_6_jobs.py"
