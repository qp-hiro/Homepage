@echo off
rem Auto-sync the Works section from Google Drive and push to GitHub Pages.
rem Registered in Task Scheduler as "Homepage Works Sync" (daily).
"C:\Users\admin\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.7_qbz5n2kfra8p0\python.exe" "D:\Git\Homepage\tools\build_works.py" --push >> "D:\Git\Homepage\tools\works_sync.log" 2>&1
