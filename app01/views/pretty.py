from django.shortcuts import render, redirect
from django.contrib import messages
from app01 import models

from app01.utils.pagination import Pagination
from app01.utils.form import UserModelForm, PrettyModelForm, PrettyEditModelForm


def pretty_list(request):
    """ IPv6地址列表 """

    data_dict = {}
    search_data = request.GET.get('q', "")
    if search_data:
        data_dict["ipv6_address__contains"] = search_data

    queryset = models.PrettyNum.objects.filter(**data_dict)

    page_object = Pagination(request, queryset)

    context = {
        "search_data": search_data,

        "queryset": page_object.page_queryset,  # 分完页的数据
        "page_string": page_object.html()  # 页码
    }
    return render(request, 'pretty_list.html', context)



from app01.utils.ipv6_api import send_to_kea_api
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import logging

logger = logging.getLogger(__name__)

def send_ipv6_address(request, nid):
    """ 发送IPv6地址到KEA API """
    if request.method == "POST":
        ipv6_obj = models.PrettyNum.objects.filter(id=nid).first()
        if not ipv6_obj:
            messages.error(request, "IPv6地址记录不存在")
            return redirect('/pretty/list/')
        
        if not ipv6_obj.mac_address:
            messages.error(request, "MAC地址为空，无法发送到API")
            return redirect('/pretty/list/')
        
        try:
            # 构建回调URL
            from django.urls import reverse
            callback_url = request.build_absolute_uri(reverse('kea_callback'))

            logger.info(f"开始发送IPv6到KEA API - 记录ID: {ipv6_obj.id}, IPv6: {ipv6_obj.ipv6_address}")

            # 调用KEA API，加入记录ID
            # 注意: send_to_kea_api 的签名为 (record_id, ipv6_address, mac_address, duid=None, callback_url=None)
            
            # 手动查找DUID进行调试
            duid_for_debug = None
            try:
                # 在设备表中查找对应的DUID
                device = models.Device.objects.filter(mac_address=ipv6_obj.mac_address).first()
                if device and device.duid:
                    duid_for_debug = device.duid
                    print(f"DEBUG: 在Device表中找到DUID: {duid_for_debug} for MAC: {ipv6_obj.mac_address}")
                else:
                    # 如果设备表没有DUID，则尝试在审批表中查找已审批的记录
                    approval = models.DeviceApproval.objects.filter(mac_address=ipv6_obj.mac_address, status=1).first()
                    if approval and approval.duid:
                        duid_for_debug = approval.duid
                        print(f"DEBUG: 在DeviceApproval表中找到DUID: {duid_for_debug} for MAC: {ipv6_obj.mac_address}")
                    else:
                        print(f"DEBUG: 在Device和DeviceApproval表中都没找到MAC {ipv6_obj.mac_address} 对应的DUID")
                        
                        # 额外调试：列出所有相关记录
                        all_devices = models.Device.objects.filter(mac_address=ipv6_obj.mac_address)
                        print(f"DEBUG: Device表中MAC为{ipv6_obj.mac_address}的记录: {list(all_devices.values_list('id', 'user', 'duid'))}")
                        
                        all_approvals = models.DeviceApproval.objects.filter(mac_address=ipv6_obj.mac_address)
                        print(f"DEBUG: DeviceApproval表中MAC为{ipv6_obj.mac_address}的记录: {list(all_approvals.values_list('id', 'user', 'duid', 'status'))}")
            except Exception as e:
                print(f"DEBUG: 查找DUID时出现异常: {str(e)}")
            
            result = send_to_kea_api(
                record_id=ipv6_obj.id,
                ipv6_address=ipv6_obj.ipv6_address,
                mac_address=ipv6_obj.mac_address,
                duid=duid_for_debug,  # 显式传递DUID
                callback_url=callback_url
            )

            logger.info(f"KEA API调用结果: {result}")
            
            # 更新发送状态
            ipv6_obj.last_send_time = timezone.now()
            ipv6_obj.api_response = json.dumps(result['response_data']) if result['response_data'] else result.get('error', '')
            
            # 检查HTTP状态码来判断发送是否成功
            if result.get('status_code') == 200:
                # HTTP发送成功，等待API回调确认最终结果
                ipv6_obj.send_status = 'pending'
                ipv6_obj.retry_count = 0
                ipv6_obj.next_retry_time = None
                ipv6_obj.save()

                messages.success(request, "发送成功！")
                logger.info(f"IPv6发送成功，设置状态为pending，等待回调")
            else:
                # HTTP发送失败
                ipv6_obj.send_status = 'failed'
                ipv6_obj.retry_count = 0
                ipv6_obj.next_retry_time = None
                ipv6_obj.save()

                error_msg = result.get('error', f"API返回失败状态码: {result.get('status_code', 'Unknown')}")
                messages.error(request, f"发送失败！错误: {error_msg}")
                return redirect('/pretty/list/')
                
        except Exception as e:
            # 发送过程中出现异常
            ipv6_obj.send_status = 'failed'
            ipv6_obj.last_send_time = timezone.now()
            ipv6_obj.retry_count = 0
            ipv6_obj.next_retry_time = None  # 已移除自动重试功能
            ipv6_obj.api_response = f"发送异常: {str(e)}"
            ipv6_obj.save()
            
            messages.error(request, f"发送IPv6地址时出现异常，如需重试请手动执行重试命令。错误: {str(e)}")

    return redirect('/pretty/list/')


def pretty_delete(request, nid):
    """ 删除IPv6地址 """
    try:
        ipv6_obj = models.PrettyNum.objects.filter(id=nid).first()
        if not ipv6_obj:
            messages.error(request, "IPv6地址记录不存在")
            return redirect('/pretty/list/')

        # 获取IPv6信息用于提示
        ipv6_info = f"用户: {ipv6_obj.user}, IPv6: {ipv6_obj.ipv6_address}"
        
        # 删除IPv6记录
        ipv6_obj.delete()
        
        messages.success(request, f"IPv6地址删除成功！({ipv6_info})")
        
    except Exception as e:
        messages.error(request, f"删除IPv6地址失败：{str(e)}")
    
    return redirect('/pretty/list/')


@csrf_exempt
def kea_callback(request):
    """
    处理KEA API的回调请求
    API通过此URL返回IPv6地址配置结果
    """
    if request.method != 'POST':
        logger.warning(f"收到非POST请求到回调URL: {request.method}")
        return JsonResponse({'success': False, 'message': '只接受POST请求'})

    # 记录请求头信息，方便调试
    logger.info(f"回调请求头: {dict(request.headers)}")
    logger.info(f"回调请求方法: {request.method}")
    logger.info(f"回调请求路径: {request.path}")

    try:
        # 获取请求数据
        if request.content_type == 'application/json':
            callback_data = json.loads(request.body)
        else:
            callback_data = request.POST.dict()

            logger.info(f"收到KEA API回调: {callback_data}")
        print(f"DEBUG 回调接收: record_id={callback_data.get('record_id')}, success={callback_data.get('success')}, mac={callback_data.get('processed_mac')}")

        # 解析回调数据 - 支持新的API格式
        # 新格式: {"success": 1, "message": "绑定成功", "record_id": "10"}
        success_value = callback_data.get('success')
        message = callback_data.get('message', '')

        # 判断是否成功（支持多种格式：1、'1'、true、True）
        is_success = (success_value == 1 or success_value == '1' or
                     success_value is True or success_value == 'true' or
                     success_value == 'True')

        # 获取记录ID
        # 首先尝试从根级别获取
        record_id = callback_data.get('record_id')

        # 如果根级别没有数据，尝试从data字段获取
        if not record_id:
            data_field = callback_data.get('data', {})
            if isinstance(data_field, dict):
                record_id = data_field.get('record_id')

        # 清理可能的前后空格
        if isinstance(record_id, str):
            record_id = record_id.strip()

        # 添加调试信息
        logger.info(f"解析后的数据 - record_id: {record_id}, success: {success_value}, message: {message}")
        logger.info(f"解析结果 - 成功: {is_success}")

        # 验证record_id
        if not record_id:
            logger.warning(f"回调数据缺少record_id，原始数据: {callback_data}")
            return JsonResponse({
                'success': False,
                'message': '缺少必要参数：record_id',
                'received_data': callback_data
            })

        # 确保record_id是整数
        try:
            record_id = int(record_id)
        except (ValueError, TypeError):
            logger.warning(f"record_id格式错误: {record_id}")
            return JsonResponse({
                'success': False,
                'message': 'record_id格式错误',
                'received_data': callback_data
            })

        # 使用record_id直接查找对应的IPv6记录
        logger.info(f"使用record_id查找IPv6记录: {record_id}")
        print(f"DEBUG 查找开始: record_id={record_id}, 当前数据库记录数量={models.PrettyNum.objects.count()}")

        ipv6_obj = models.PrettyNum.objects.filter(id=record_id).first()
        print(f"DEBUG 通过ID查找结果: {'找到' if ipv6_obj else '未找到'}")

        # 如果通过record_id找不到记录，尝试通过MAC地址查找（备用方案）
        if not ipv6_obj and 'processed_mac' in callback_data:
            mac_address = callback_data['processed_mac']
            logger.info(f"通过record_id未找到记录，尝试通过MAC地址查找: {mac_address}")
            print(f"DEBUG MAC地址查找: {mac_address}")
            ipv6_obj = models.PrettyNum.objects.filter(mac_address=mac_address).first()
            if ipv6_obj:
                logger.info(f"通过MAC地址找到记录，ID={ipv6_obj.id}, 原始record_id={record_id}")
                print(f"DEBUG MAC查找成功: 找到ID={ipv6_obj.id}的记录")
            else:
                print(f"DEBUG MAC查找失败: 未找到MAC={mac_address}的记录")

        # 如果还是找不到记录，尝试查找最近创建的记录（兜底方案）
        if not ipv6_obj:
            logger.info("尝试查找最近创建的IPv6记录进行匹配")
            print(f"DEBUG 兜底查找: 查找最近的IPv6记录")
            recent_records = models.PrettyNum.objects.filter(send_status='pending').order_by('-id')[:3]
            for recent_record in recent_records:
                print(f"DEBUG 检查记录: ID={recent_record.id}, MAC={recent_record.mac_address}, IPv6={recent_record.ipv6_address}")
                # 检查MAC地址是否匹配
                if 'processed_mac' in callback_data and recent_record.mac_address == callback_data['processed_mac']:
                    ipv6_obj = recent_record
                    logger.info(f"通过MAC地址匹配找到最近记录，ID={ipv6_obj.id}")
                    print(f"DEBUG 兜底成功: 通过MAC匹配找到ID={ipv6_obj.id}")
                    break

        if not ipv6_obj:
            logger.warning(f"未找到ID为 {record_id} 的IPv6记录")

            # 尝试查找所有记录进行调试
            all_records = models.PrettyNum.objects.all()[:10]
            logger.info(f"数据库中的IPv6记录示例: {[f'ID:{r.id}, IPv6:{r.ipv6_address}, MAC:{r.mac_address}' for r in all_records]}")

            # 额外调试：查找是否有匹配的MAC地址记录
            if 'processed_mac' in callback_data:
                mac_records = models.PrettyNum.objects.filter(mac_address=callback_data['processed_mac'])[:5]
                logger.info(f"通过MAC地址找到的记录: {[f'ID:{r.id}, IPv6:{r.ipv6_address}' for r in mac_records]}")

            return JsonResponse({
                'success': False,
                'message': '未找到对应记录',
                'searched_record_id': record_id,
                'callback_data': callback_data
            })

        # 更新记录状态
        ipv6_obj.last_send_time = timezone.now()
        ipv6_obj.api_response = json.dumps(callback_data)

        logger.info(f"更新记录ID {record_id} 的状态 - 原始状态: {ipv6_obj.send_status}, 成功: {is_success}")

        if is_success:
            # API绑定成功
            ipv6_obj.send_status = 'bound'  # 绑定成功
            ipv6_obj.retry_count = 0
            ipv6_obj.next_retry_time = None
            logger.info(f"记录ID {record_id} 的IPv6绑定成功，状态更新为: bound")
        else:
            # API绑定失败，保存错误信息
            ipv6_obj.send_status = 'bind_failed'  # 绑定失败
            ipv6_obj.retry_count = 0
            ipv6_obj.next_retry_time = None
            # 将错误信息保存到api_response中
            error_info = {
                'error_message': message,
                'callback_data': callback_data
            }
            ipv6_obj.api_response = json.dumps(error_info)
            logger.warning(f"记录ID {record_id} 的IPv6绑定失败，状态更新为: bind_failed, 错误: {message}")

        ipv6_obj.save()
        logger.info(f"记录ID {record_id} 更新完成，最终状态: {ipv6_obj.send_status}")

        # 提取IPv6后64位用于响应
        ipv6_last_64 = ''
        if ipv6_obj.ipv6_address:
            from app01.utils.ipv6_api import extract_ipv6_last_64_bits
            ipv6_last_64 = extract_ipv6_last_64_bits(ipv6_obj.ipv6_address) or ''

        # 返回响应给API - 使用JSON格式
        response_data = {
            'success': True,
            'message': '回调处理完成',
            'record_id': str(record_id),
            'processed_ipv6_suffix': ipv6_last_64,
            'processed_mac': ipv6_obj.mac_address or '',
            'result': 'success' if is_success else 'failed'
        }
        
        logger.info(f"返回给API的响应: {response_data}")
        return JsonResponse(response_data)

    except Exception as e:
        logger.error(f"处理KEA回调时出错: {str(e)}", exc_info=True)

        # 尝试提供更详细的错误信息
        error_details = {
            'error_type': type(e).__name__,
            'error_message': str(e),
            'callback_data_received': True if 'callback_data' in locals() else False,
            'variables_defined': {
                'ipv6_suffix': 'ipv6_suffix' in locals(),
                'mac_address': 'mac_address' in locals(),
                'is_success': 'is_success' in locals()
            }
        }

        return JsonResponse({
            'success': False,
            'message': f'处理回调出错: {str(e)}',
            'error_details': error_details
        })


@csrf_exempt
def device_offline_callback(request):
    """
    处理设备下线API的回调请求
    API通过此URL返回设备下线结果
    """
    if request.method != 'POST':
        logger.warning(f"收到非POST请求到设备下线回调URL: {request.method}")
        return JsonResponse({'success': False, 'message': '只接受POST请求'})

    # 记录请求头信息，方便调试
    logger.info(f"设备下线回调请求头: {dict(request.headers)}")
    logger.info(f"设备下线回调请求方法: {request.method}")
    logger.info(f"设备下线回调请求路径: {request.path}")

    try:
        # 获取请求数据
        if request.content_type == 'application/json':
            callback_data = json.loads(request.body)
        else:
            callback_data = request.POST.dict()

        logger.info(f"收到设备下线API回调: {callback_data}")

        # 解析回调数据
        success_value = callback_data.get('success')
        result_value = callback_data.get('result')
        message = callback_data.get('message', '')
        
        # 获取设备ID - 支持device_id或record_id字段
        device_id = callback_data.get('device_id') or callback_data.get('record_id')

        # 判断是否成功（需要同时检查success和result字段）
        success_check = (success_value == 1 or success_value == '1' or
                        success_value is True or success_value == 'true' or
                        success_value == 'True')
        
        # 如果有result字段，还需要检查result是否为success
        if result_value is not None:
            result_check = (result_value == 'success' or result_value == 'Success' or
                           result_value == 1 or result_value == '1' or result_value is True)
            is_success = success_check and result_check
            logger.info(f"设备下线回调检查: success={success_value}({success_check}), result={result_value}({result_check}), 最终={is_success}")
        else:
            is_success = success_check
            logger.info(f"设备下线回调检查: success={success_value}({success_check}), 无result字段, 最终={is_success}")

        # 验证device_id
        if not device_id:
            logger.warning(f"设备下线回调数据缺少device_id/record_id，原始数据: {callback_data}")
            return JsonResponse({
                'success': False,
                'message': '缺少必要参数：device_id',
                'received_data': callback_data
            })

        # 确保device_id是整数
        try:
            device_id = int(device_id)
        except (ValueError, TypeError):
            logger.warning(f"device_id格式错误: {device_id}")
            return JsonResponse({
                'success': False,
                'message': 'device_id格式错误',
                'received_data': callback_data
            })

        # 使用device_id查找对应的设备记录
        logger.info(f"使用device_id查找设备记录: {device_id}")

        device_obj = models.Device.objects.filter(id=device_id).first()

        if not device_obj:
            logger.warning(f"未找到ID为 {device_id} 的设备记录")
            return JsonResponse({
                'success': False,
                'message': '未找到对应设备记录',
                'searched_device_id': device_id
            })

        # 更新设备状态
        device_obj.api_response = json.dumps(callback_data)

        logger.info(f"更新设备ID {device_id} 的下线状态 - 成功: {is_success}")

        # 返回响应给API
        if is_success:
            # 下线成功 - 更新设备状态为offline
            device_obj.status = 'offline'
            device_obj.save()
            
            # 同时处理对应的IPv6记录
            if device_obj.mac_address:
                ipv6_records = models.PrettyNum.objects.filter(mac_address=device_obj.mac_address)
                for ipv6_obj in ipv6_records:
                    # 可以选择删除IPv6记录或者标记为已下线
                    # 这里我们选择更新绑定状态为'offline'（如果需要的话）
                    ipv6_obj.api_response = json.dumps({
                        'status': 'device_offline',
                        'device_id': device_id,
                        'timestamp': callback_data.get('timestamp', ''),
                        'message': f'设备{device_id}已下线'
                    })
                    ipv6_obj.save()
                    logger.info(f"IPv6记录 {ipv6_obj.id}({ipv6_obj.ipv6_address}) 已更新为设备下线状态")
            
            logger.info(f"设备ID {device_id} 下线成功，状态已更新为offline，消息: {message}")
            return JsonResponse({
                'success': True,
                'message': f'设备下线成功: {message}',
                'device_id': device_id
            })
        else:
            # 下线失败 - 保持设备状态为online
            device_obj.save()  # 只保存api_response
            logger.warning(f"设备ID {device_id} 下线失败，状态保持online，消息: {message}")
            return JsonResponse({
                'success': False,
                'message': f'设备下线失败: {message}',
                'device_id': device_id
            })

    except Exception as e:
        logger.error(f"处理设备下线回调时出错: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f'处理设备下线回调出错: {str(e)}'
        })


@csrf_exempt
def kea_callback_test(request):
    """
    测试KEA回调功能是否正常
    GET请求返回测试信息，POST请求模拟回调处理
    """
    if request.method == 'GET':
        return JsonResponse({
            'success': True,
            'message': 'KEA回调测试端点正常',
            'url': request.build_absolute_uri(),
            'method': 'GET',
            'timestamp': timezone.now().isoformat()
        })

    elif request.method == 'POST':
        # 模拟处理回调
        try:
            if request.content_type == 'application/json':
                test_data = json.loads(request.body)
            else:
                test_data = {'message': 'POST请求收到', 'timestamp': timezone.now().isoformat()}

            return JsonResponse({
                'success': True,
                'message': '回调测试成功',
                'received_data': test_data,
                'timestamp': timezone.now().isoformat()
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'测试出错: {str(e)}'
            })

    return JsonResponse({'success': False, 'message': '不支持的请求方法'})
