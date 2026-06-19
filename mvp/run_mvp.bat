@echo off
cd /d "%~dp0"
echo Installing MVP dependencies...
pip install streamlit openai -q
echo.
echo Starting AI Discovery Companion...
echo Open your browser at: http://localhost:8501
echo.
streamlit run app.py
pause
