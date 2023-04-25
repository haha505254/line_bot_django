
重啟後
sudo iptables -F
sudo iptables -X
. /home/ubuntu/linebot/venv_env/bin/activate && cd /home/ubuntu/linebot/line_bot_django/my_line_bot
nohup gunicorn my_line_bot.wsgi:application --bind 127.0.0.1:8000 &
tail -f nohup.out
sudo lsof -i :8000 檢查是否
如果 PID 為 12345
sudo kill 12345

