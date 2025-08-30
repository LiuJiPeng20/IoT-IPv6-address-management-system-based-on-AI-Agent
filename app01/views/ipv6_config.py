from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from app01 import models
from app01.utils.pagination import Pagination
from app01.utils.form import IPv6ConfigModelForm, IPv6ConfigEditModelForm
import json
import requests
import logging

logger = logging.getLogger(__name__)


def ipv6_config_list(request):
    """ IPv6地址配置列表 """
    # 权限检查
    if not request.session.get("info"):
        return redirect('/login/')

    # 构造搜索
    data_dict = {}
    search_data = request.GET.get('q', "")
    if search_data:
        data_dict["vlan_id__contains"] = search_data

    queryset = models.IPv6Config.objects.filter(**data_dict).order_by('-create_time')

    page_object = Pagination(request, queryset, page_size=10)
    context = {
        "search_data": search_data,
        "queryset": page_object.page_queryset,
        "page_string": page_object.html(),
    }
    return render(request, 'ipv6_config_list.html', context)


def ipv6_config_add(request):
    """ 添加IPv6地址配置 """
    # 权限检查
    if not request.session.get("info"):
        return redirect('/login/')

    if request.method == "GET":
        # 默认设置管理员名为当前登录的管理员
        admin_name = request.session.get("info", {}).get("name", "")
        form = IPv6ConfigModelForm(initial={'admin_name': admin_name})
        return render(request, 'ipv6_config_add.html', {"form": form})

    form = IPv6ConfigModelForm(data=request.POST)
    if form.is_valid():
        # 检查VLAN是否重复
        vlan_id = form.cleaned_data['vlan_id']
        if models.IPv6Config.objects.filter(vlan_id=vlan_id).exists():
            form.add_error('vlan_id', f'VLAN {vlan_id} 已存在')
            return render(request, 'ipv6_config_add.html', {"form": form})
        
        form.save()
        messages.success(request, f"IPv6配置添加成功！VLAN {vlan_id}")
        return redirect('/ipv6/config/list/')
        
    return render(request, 'ipv6_config_add.html', {"form": form})


def ipv6_config_edit(request, nid):
    """ 编辑IPv6地址配置 """
    # 权限检查
    if not request.session.get("info"):
        return redirect('/login/')

    row_object = models.IPv6Config.objects.filter(id=nid).first()
    if not row_object:
        messages.error(request, "配置记录不存在")
        return redirect('/ipv6/config/list/')

    if request.method == "GET":
        form = IPv6ConfigEditModelForm(instance=row_object)
        return render(request, 'ipv6_config_edit.html', {"form": form})

    form = IPv6ConfigEditModelForm(data=request.POST, instance=row_object)
    if form.is_valid():
        form.save()
        messages.success(request, f"IPv6配置更新成功！VLAN {form.cleaned_data['vlan_id']}")
        return redirect('/ipv6/config/list/')

    return render(request, 'ipv6_config_edit.html', {"form": form})


def ipv6_config_send(request, nid):
    """ 发送IPv6配置到API """
    # 权限检查
    if not request.session.get("info"):
        return redirect('/login/')

    if request.method == "POST":
        config_obj = models.IPv6Config.objects.filter(id=nid).first()
        if not config_obj:
            messages.error(request, "配置记录不存在")
            return redirect('/ipv6/config/list/')

        try:
            # 使用专门的API工具函数发送
            from app01.utils.ipv6_config_api import send_ipv6_config_to_api
            
            # 构建回调URL
            callback_url = request.build_absolute_uri('/api/ipv6/config/callback/')

            # 调用API发送函数
            result = send_ipv6_config_to_api(config_obj, callback_url)

            # 更新发送状态
            config_obj.api_response = json.dumps({
                'status_code': result.get('status_code'),
                'response_data': result.get('response_data'),
                'error': result.get('error'),
                'timestamp': timezone.now().isoformat()
            })

            if result['success']:
                config_obj.send_status = 'sent'
                config_obj.save()
                messages.info(request, f"IPv6配置已发送，正在等待API处理结果...VLAN {config_obj.vlan_id}")
            else:
                config_obj.send_status = 'failed'
                config_obj.save()
                error_msg = result.get('error', f"HTTP状态码: {result.get('status_code', 'Unknown')}")
                messages.error(request, f"发送失败！{error_msg}")

        except Exception as e:
            config_obj.send_status = 'failed'
            config_obj.api_response = f"发送异常: {str(e)}"
            config_obj.save()
            messages.error(request, f"发送失败：{str(e)}")

    return redirect('/ipv6/config/list/')


@csrf_exempt
def ipv6_config_callback(request):
    """
    处理IPv6配置API的回调请求
    """
    if request.method != 'POST':
        logger.warning(f"收到非POST请求到IPv6配置回调URL: {request.method}")
        return JsonResponse({'success': False, 'message': '只接受POST请求'})

    try:
        # 获取请求数据
        if request.content_type == 'application/json':
            callback_data = json.loads(request.body)
        else:
            callback_data = request.POST.dict()

        logger.info(f"收到IPv6配置API回调: {callback_data}")

        # 使用专门的回调处理函数
        from app01.utils.ipv6_config_api import process_config_callback, format_conflict_message
        
        # 处理回调数据
        callback_result = process_config_callback(callback_data)
        
        success_value = callback_result['success']
        config_id = callback_result['config_id']
        message = callback_result['message']
        conflicts = callback_result['conflicts']
        
        # 判断是否成功
        is_success = success_value

        # 验证config_id
        if not config_id:
            logger.warning(f"IPv6配置回调数据缺少config_id，原始数据: {callback_data}")
            return JsonResponse({
                'success': False,
                'message': '缺少必要参数：config_id',
                'received_data': callback_data
            })

        # 确保config_id是整数
        try:
            config_id = int(config_id)
        except (ValueError, TypeError):
            logger.warning(f"config_id格式错误: {config_id}")
            return JsonResponse({
                'success': False,
                'message': 'config_id格式错误',
                'received_data': callback_data
            })

        # 查找配置记录
        config_obj = models.IPv6Config.objects.filter(id=config_id).first()
        if not config_obj:
            logger.warning(f"未找到ID为 {config_id} 的配置记录")
            return JsonResponse({
                'success': False,
                'message': '未找到对应配置记录',
                'searched_config_id': config_id
            })

        # 更新配置状态
        config_obj.api_response = json.dumps(callback_data)

        if is_success:
            # 发送成功
            config_obj.send_status = 'success'
            config_obj.save()
            logger.info(f"IPv6配置ID {config_id} 发送成功，消息: {message}")
            
            return JsonResponse({
                'success': True,
                'message': 'IPv6配置发送成功'
            })
        else:
            # 发送失败，处理冲突信息
            config_obj.send_status = 'failed'
            config_obj.save()
            
            # 使用工具函数格式化冲突信息
            conflict_msg = format_conflict_message(conflicts) if conflicts else (message or "发送失败")
            
            logger.warning(f"IPv6配置ID {config_id} 发送失败，消息: {conflict_msg}")
            
            return JsonResponse({
                'success': False,
                'message': f'发送失败：{conflict_msg}'
            })

    except Exception as e:
        logger.error(f"处理IPv6配置回调时出错: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f'处理回调出错: {str(e)}'
        })
