Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "Checking git tree..."
$status = git status --porcelain
if ($status) {
    Write-Error "Git tree is dirty. Commit or stash changes before deploy."
    exit 1
}

Write-Host "Running backend tests..."
Push-Location backend
try {
    ..\env\Scripts\python.exe manage.py test
    ..\env\Scripts\python.exe manage.py spectacular --file schema.yml --validate
}
finally {
    Pop-Location
}

Write-Host "Running frontend lint/test/build..."
Push-Location frontend
try {
    npm.cmd run lint
    npm.cmd run test:ci
    npm.cmd run build:ci
}
finally {
    Pop-Location
}

Write-Host "Predeploy checks passed."
