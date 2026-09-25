# download_results.ps1
# Helper script to download all simulation results from server to local PC

$server = "user13@10.1.73.18"
$remote_dir = "~/validation"
$local_dir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " DOWNLOADING RESULTS FROM SERVER: $server" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Download all result CSVs
Write-Host "`n[1/3] Downloading result CSVs..." -ForegroundColor Yellow
scp "$server`:$remote_dir/results_*.csv" "$local_dir\results\"

# 2. Download active model configuration
Write-Host "`n[2/3] Downloading configuration files..." -ForegroundColor Yellow
scp "$server`:$remote_dir/*.conf" "$local_dir\scripts\"

# 3. Download overnight logs
Write-Host "`n[3/3] Downloading overnight logs..." -ForegroundColor Yellow
scp -r "$server`:$remote_dir/overnight_logs" "$local_dir\results\"

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host " DOWNLOAD COMPLETE! Checking results..." -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green

python "$local_dir\scripts\compare_phase0.py"
python "$local_dir\scripts\analyze_results.py" --phase 1
