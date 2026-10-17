@echo off
SET BASE_DIR=D:\DotNetCoreProjects\OICOCR\OICOCRcd /d %BASE_DIR%

call venv\Scripts\activate.bat
python main.py >> logs\main.log 2>&1
deactivate
