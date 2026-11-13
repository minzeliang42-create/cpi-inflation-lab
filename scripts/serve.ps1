Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
python -m http.server 8765 --bind 127.0.0.1 --directory dist
