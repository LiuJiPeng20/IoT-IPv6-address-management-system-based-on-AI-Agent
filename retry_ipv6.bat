@echo off
cd /d "F:\研究方向\DHCP\Python最新Web开发-课件\Python最新Web开发-课件\day18 Django开发\代码\day16\"
python manage.py retry_ipv6_send >> ipv6_retry.log 2>&1
echo %date% %time% - IPv6閲嶈瘯浠诲姟瀹屾垚 >> ipv6_retry.log
