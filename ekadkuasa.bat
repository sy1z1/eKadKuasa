@echo off
cd / d 'C:\inetpub\wwwroot\eKadKuasa2\eKadKuasa'
py manage.py runserver 192.168.137.1:8000
pause