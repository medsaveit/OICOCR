@echo off
SET BASE_DIR=D:\DotNetCoreProjects\OICOCR\OICOCRcd /d %BASE_DIR%

call venv\Scripts\activate.bat
python ocr_main.py >> logs\ocr.log 2>&1
deactivate
