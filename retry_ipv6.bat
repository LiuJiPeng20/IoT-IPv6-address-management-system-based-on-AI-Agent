@echo off
cd /d "F:\�о�����\DHCP\Python����Web����-�μ�\Python����Web����-�μ�\day18 Django����\����\day16\"
python manage.py retry_ipv6_send >> ipv6_retry.log 2>&1
echo %date% %time% - IPv6重试任务完成 >> ipv6_retry.log
