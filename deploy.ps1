param(
    [string]$Message = "update",
    [switch]$FrontendOnly
)

$Server = "root@110.42.217.122"
$ServerPath = "/root/Lord-King"

Set-Location $PSScriptRoot

git add .
git commit -m $Message
git push origin main
if (-not $?) {
    Write-Error "push 失败，终止部署"
    exit 1
}

if ($FrontendOnly) {
    Write-Host "只更新前端..."
    ssh $Server "cd $ServerPath && git pull && docker compose restart nginx"
} else {
    Write-Host "全量部署..."
    ssh $Server "cd $ServerPath && git pull && docker compose up -d --build"
}

if ($?) {
    Write-Host "部署完成"
} else {
    Write-Error "服务器部署失败，请 SSH 上去检查日志"
}
