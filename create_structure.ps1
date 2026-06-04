$root = "supportpilot"

$folders = @(
    "$root",
    "$root\orchestrator",
    "$root\tools",
    "$root\knowledge_base",
    "$root\api",
    "$root\dashboard"
)

foreach ($folder in $folders) {
    New-Item -ItemType Directory -Path $folder -Force | Out-Null
}

$files = @(
    "$root\orchestrator\agent.py",
    "$root\orchestrator\state.py",
    "$root\tools\classify_ticket.py",
    "$root\tools\search_kb.py",
    "$root\tools\get_order_status.py",
    "$root\tools\draft_reply.py",
    "$root\tools\send_reply.py",
    "$root\knowledge_base\faqs.json",
    "$root\knowledge_base\ingest.py",
    "$root\api\routes.py",
    "$root\api\models.py",
    "$root\dashboard\index.html",
    "$root\logger.py",
    "$root\exceptions.py",
    "$root\main.py"
)

foreach ($file in $files) {
    New-Item -ItemType File -Path $file -Force | Out-Null
}

Write-Host "Project structure created successfully!"