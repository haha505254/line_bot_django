
nohup gunicorn my_line_bot.wsgi:application --bind 127.0.0.1:8000 &
tail -f nohup.out
sudo lsof -i :8000
如果 PID 為 12345
sudo kill 12345