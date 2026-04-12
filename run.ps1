Set-Location $PSScriptRoot
.\.venv\Scripts\python.exe -c "import sys; print('PY=', sys.executable)"
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
