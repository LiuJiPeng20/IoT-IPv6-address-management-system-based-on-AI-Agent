import requests
import json
import logging
from datetime import datetime, timedelta
from django.utils import timezone

# 配置日志
logger = logging.getLogger(__name__)

def extract_ipv6_last_64_bits(ipv6_address):
    """
    提取IPv6地址的后64位
    
    Args:
        ipv6_address (str): 完整的IPv6地址
        
    Returns:
        str: IPv6地址的后64位
    """
    try:
        # 移除可能的压缩格式，展开完整IPv6地址
        import ipaddress
        ipv6_obj = ipaddress.IPv6Address(ipv6_address)
        full_ipv6 = str(ipv6_obj.exploded)  # 获取完整格式的IPv6地址
        
        # IPv6地址格式: xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx:xxxx
        # 后64位就是后4个分组
        parts = full_ipv6.split(':')
        last_64_bits = ':'.join(parts[4:])  # 取后4个分组
        
        return last_64_bits
        
    except Exception as e:
        logger.error(f"提取IPv6后64位失败: {e}")
        return None


def send_to_kea_api(record_id, ipv6_address, mac_address, duid=None, callback_url=None):
    """
    发送完整的IPv6地址和MAC地址到KEA API，并包含对应的DUID信息

    Args:
        record_id (int): 数据库记录ID
        ipv6_address (str): 完整的IPv6地址
        mac_address (str): MAC地址
        duid (str): 设备DUID，如果不提供则尝试通过MAC地址查找
        callback_url (str): 回调URL，如果不提供则自动生成

    Returns:
        dict: 包含发送结果的字典
        {
            'success': bool,
            'status_code': int,
            'response_data': dict,
            'error': str
        }
    """
    try:
        # 验证IPv6地址格式
        if not ipv6_address:
            return {
                'success': False,
                'status_code': None,
                'response_data': None,
                'error': 'IPv6地址不能为空'
            }

        # 处理DUID：优先使用传入参数，如果没有则通过MAC地址查找
        if not duid and mac_address:
            try:
                from app01 import models
                # 在设备表中查找对应的DUID
                device = models.Device.objects.filter(mac_address=mac_address).first()
                if device and device.duid:
                    duid = device.duid
                    logger.info(f"通过MAC地址 {mac_address} 找到对应的DUID: {duid}")
                else:
                    # 如果设备表没有DUID，则尝试在审批表中查找已审批的记录
                    approval = models.DeviceApproval.objects.filter(mac_address=mac_address, status=1).first()
                    if approval and approval.duid:
                        duid = approval.duid
                        logger.info(f"通过审批表根据MAC {mac_address} 找到对应的DUID: {duid}")
                    else:
                        logger.info(f"MAC地址 {mac_address} 在设备表和审批表中均未找到对应的DUID记录")
            except Exception as e:
                logger.warning(f"查找DUID时出现异常: {str(e)}")

        # 如果仍然没有DUID，记录警告
        if not duid:
            logger.warning(f"无法获取DUID信息，MAC地址: {mac_address}")

        # 准备发送数据
        api_url = "http://222.204.3.179:3003/webhook/kea"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "IoT-IPv6-Management-System/1.0"
        }

        # 如果没有提供回调URL，生成默认的回调URL
        if not callback_url:
            callback_url = "http://your-server-ip:8000/api/kea/callback/"  # 替换为实际的服务器地址

        payload = {
            "record_id": record_id,  # 添加记录ID
            "ipv6_address": ipv6_address,  # 完整的IPv6地址（128位）
            "mac_address": mac_address,
            "duid": duid,  # 添加DUID字段，如果未找到则为None
            "timestamp": datetime.now().isoformat(),
            "callback_url": callback_url  # 添加回调URL
        }

        logger.info(f"发送到KEA API: {api_url}")
        logger.info(f"发送的payload数据: record_id={record_id}, ipv6_address={ipv6_address}, mac_address={mac_address}")
        print(f"DEBUG API发送: record_id={record_id}, ipv6_address={ipv6_address}, mac_address={mac_address}")
        
        # 发送请求（设置10秒超时）
        response = requests.post(
            api_url,
            headers=headers,
            data=json.dumps(payload),
            timeout=10
        )
        
        # 解析响应
        try:
            response_data = response.json()
        except:
            response_data = {"raw_response": response.text}
        
        # 检查API返回的成功标志
        api_success = False
        if response.status_code == 200:
            # 检查返回数据中的成功标志
            if isinstance(response_data, dict):
                # 可能的成功标志字段
                success_indicators = [
                    response_data.get('success'),
                    response_data.get('status'),
                    response_data.get('result'),
                    response_data.get('code')
                ]
                # 检查是否有成功标志 (支持多种成功标志格式)
                api_success = any(
                    indicator == 1 or indicator == '1' or indicator is True or 
                    indicator == 'true' or indicator == 'success' or indicator == 'Success'
                    for indicator in success_indicators if indicator is not None
                )
        
        logger.info(f"API响应: 状态码={response.status_code}, 数据={response_data}, 成功={api_success}")

        # 调试信息：记录具体的判断过程
        if not api_success and response.status_code == 200:
            logger.warning(f"KEA API返回200但判断为失败，响应数据: {response_data}")
            logger.warning(f"成功指标检查: {success_indicators}")

        return {
            'success': api_success,
            'status_code': response.status_code,
            'response_data': response_data,
            'error': None
        }
        
    except requests.exceptions.Timeout:
        error_msg = "API请求超时（10秒）"
        logger.error(error_msg)
        return {
            'success': False,
            'status_code': None,
            'response_data': None,
            'error': error_msg
        }
        
    except requests.exceptions.ConnectionError:
        error_msg = "无法连接到API服务器"
        logger.error(error_msg)
        return {
            'success': False,
            'status_code': None,
            'response_data': None,
            'error': error_msg
        }
        
    except Exception as e:
        error_msg = f"发送API请求时出错: {str(e)}"
        logger.error(error_msg)
        return {
            'success': False,
            'status_code': None,
            'response_data': None,
            'error': error_msg
        }


def send_device_offline_to_api(device_id, duid, mac_address):
    """
    发送设备下线请求到KEA API，并包含对应的IPv6地址信息

    Args:
        device_id (int): 设备ID
        duid (str): 设备DUID
        mac_address (str): 设备MAC地址

    Returns:
        dict: 包含发送结果的字典
        {
            'success': bool,
            'status_code': int,
            'response_data': dict,
            'error': str
        }
    """
    try:
        # 通过MAC地址查找对应的完整IPv6地址
        ipv6_address = None
        if mac_address:
            try:
                from app01 import models
                # 在IPv6地址表中查找对应的记录
                ipv6_record = models.PrettyNum.objects.filter(mac_address=mac_address).first()
                if ipv6_record and ipv6_record.ipv6_address:
                    # 获取完整的IPv6地址
                    ipv6_address = ipv6_record.ipv6_address
                    logger.info(f"通过MAC地址 {mac_address} 找到对应的完整IPv6地址: {ipv6_address}")
                else:
                    logger.info(f"MAC地址 {mac_address} 在IPv6地址表中未找到对应的记录")
            except Exception as e:
                logger.warning(f"查找IPv6地址时出现异常: {str(e)}")

        # 准备发送数据
        api_url = "http://222.204.3.179:3003/webhook/kea"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "IoT-IPv6-Management-System/1.0"
        }

        # 如果没有提供回调URL，生成默认的回调URL
        from django.urls import reverse
        from django.conf import settings
        callback_url = f"http://your-server-ip:8000/api/device/offline/callback/"

        payload = {
            "device_id": device_id,
            "duid": duid,
            "mac_address": mac_address,
            "ipv6_address": ipv6_address,  # 完整的IPv6地址（128位）
            "offline": "delete",  # 下线操作标识
            "timestamp": datetime.now().isoformat(),
            "callback_url": callback_url,  # 设备下线回调URL
        }

        logger.info(f"发送设备下线请求到API: {api_url}, 数据: {payload}")

        # 发送请求（设置10秒超时）
        response = requests.post(
            api_url,
            headers=headers,
            data=json.dumps(payload),
            timeout=10
        )

        # 解析响应
        try:
            response_data = response.json()
        except:
            response_data = {"raw_response": response.text}

        # 检查API返回的成功标志
        api_success = False
        if response.status_code == 200:
            # 检查返回数据中的成功标志
            if isinstance(response_data, dict):
                # 检查success字段
                success_field = response_data.get('success')
                result_field = response_data.get('result')
                
                # success字段必须为true/True/1/'1'
                success_check = success_field in [True, 'true', 1, '1']
                
                # 如果有result字段，则还需要检查result是否为success
                if result_field is not None:
                    result_check = result_field in ['success', 'Success', 1, '1', True]
                    api_success = success_check and result_check
                    logger.info(f"设备下线检查结果: success={success_field}({success_check}), result={result_field}({result_check}), 最终={api_success}")
                else:
                    api_success = success_check
                    logger.info(f"设备下线检查结果: success={success_field}({success_check}), 无result字段, 最终={api_success}")

        logger.info(f"设备下线API响应: 状态码={response.status_code}, 数据={response_data}, 成功={api_success}")

        return {
            'success': api_success,
            'status_code': response.status_code,
            'response_data': response_data,
            'error': None
        }

    except requests.exceptions.Timeout:
        error_msg = "设备下线API请求超时（10秒）"
        logger.error(error_msg)
        return {
            'success': False,
            'status_code': None,
            'response_data': None,
            'error': error_msg
        }

    except requests.exceptions.ConnectionError:
        error_msg = "无法连接到设备下线API服务器"
        logger.error(error_msg)
        return {
            'success': False,
            'status_code': None,
            'response_data': None,
            'error': error_msg
        }

    except Exception as e:
        error_msg = f"发送设备下线API请求时出错: {str(e)}"
        logger.error(error_msg)
        return {
            'success': False,
            'status_code': None,
            'response_data': None,
            'error': error_msg
        }


# 定时重试功能已移除，保留API发送功能
