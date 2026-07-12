@echo off
rem Task Scheduler: intraday quote refresh (BIST hours, every 15 min)
cd /d C:\Users\RasaComputer\Desktop\bist
python -m tefaslab intraday >> logs\intraday.log 2>&1
