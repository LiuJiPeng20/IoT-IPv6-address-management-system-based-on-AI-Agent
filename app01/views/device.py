from django.shortcuts import render, redirect, HttpResponse
from django.contrib import messages
from django.utils import timezone
from app01 import models
from app01.utils.pagination import Pagination
from app01.utils.form import DeviceModelForm
from app01.utils.ipv6_generator import generate_ipv6, validate_mac_address
import json

def device_list(request):
    """ 设备列表 """
    # 权限检查
    if not request.session.get("info"):
        return redirect('/login/') # 非管理员重定向到登录页

    # 构造搜索
    data_dict = {}
    search_data = request.GET.get('q', "")
    if search_data:
        data_dict["duid__contains"] = search_data
        data_dict["mac_address__contains"] = search_data # 允许搜索MAC地址

    queryset = models.Device.objects.filter(**data_dict).order_by('-create_time') # 按审批时间倒序排列

    page_object = Pagination(request, queryset, page_size=10)
    context = {
        "search_data": search_data,
        "queryset": page_object.page_queryset,
        "page_string": page_object.html(),
    }
    return render(request, 'device_list.html', context)


def device_offline(request, nid):
    """ 设备下线 """
    # 权限检查
    if not request.session.get("info"):
        return redirect('/login/') # 非管理员重定向到登录页

    if request.method == "GET":
        try:
            device_obj = models.Device.objects.filter(id=nid).first()
            if not device_obj:
                messages.error(request, "设备不存在")
                return redirect('/device/list/')

            # 获取设备信息用于提示
            device_info = f"用户: {device_obj.user}, MAC: {device_obj.mac_address}"

            # 发送下线请求到API
            from app01.utils.ipv6_api import send_device_offline_to_api
            from django.urls import reverse
            from django.contrib.sites.shortcuts import get_current_site

            # 构建回调URL
            try:
                callback_url = f"http://your-server-ip:8000/api/device/offline/callback/"
            except:
                callback_url = "http://your-server-ip:8000/api/device/offline/callback/"

            result = send_device_offline_to_api(
                device_id=device_obj.id,
                duid=device_obj.duid,
                mac_address=device_obj.mac_address
            )

            # 检查HTTP发送是否成功（200状态码表示请求成功发送）
            if result.get('status_code') == 200:
                # HTTP发送成功，立即更新设备状态为下线
                device_obj.status = 'offline'
                device_obj.save()
                
                # 同时处理对应的IPv6记录
                if device_obj.mac_address:
                    ipv6_records = models.PrettyNum.objects.filter(mac_address=device_obj.mac_address)
                    for ipv6_obj in ipv6_records:
                        ipv6_obj.api_response = json.dumps({
                            'status': 'device_offline',
                            'device_id': device_obj.id,
                            'timestamp': timezone.now().isoformat(),
                            'message': f'设备{device_obj.id}已下线'
                        })
                        ipv6_obj.save()
                
                messages.success(request, f"设备下线成功！({device_info})")
            else:
                # HTTP发送失败
                error_msg = result.get('error', f"API返回失败状态码: {result.get('status_code', 'Unknown')}")
                messages.error(request, f"设备下线请求发送失败！({device_info}) 错误: {error_msg}")

        except Exception as e:
            messages.error(request, f"发送设备下线请求时出现异常：{str(e)}")

    return redirect('/device/list/')
