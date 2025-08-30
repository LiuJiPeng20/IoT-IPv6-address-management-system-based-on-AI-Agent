import requests
import json
import logging
from datetime import datetime
from django.utils import timezone

# 配置日志
logger = logging.getLogger(__name__)


def send_ipv6_config_to_api(config_obj, callback_url=None):
    """
    发送IPv6配置到KEA-ADD API
    
    Args:
        config_obj: IPv6Config模型实例
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
        # 验证配置对象
        if not config_obj:
            return {
                'success': False,
                'status_code': None,
                'response_data': None,
                'error': 'IPv6配置对象不能为空'
            }

        # 准备发送数据
        api_url = "http://222.204.3.179:3003/webhook/kea-add"
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "IPv6-Config-System/1.0"
        }

        # 如果没有提供回调URL，生成默认的回调URL
        if not callback_url:
            callback_url = "http://your-server-ip:8000/api/ipv6/config/callback/"

        # 构建发送的payload数据
        payload = {
            "config_id": config_obj.id,
            "admin_name": config_obj.admin_name,
            "vlan_id": config_obj.vlan_id,
            "gateway": config_obj.gateway,
            "dhcp_relay": config_obj.dhcp_relay,
            "timestamp": timezone.now().isoformat(),
            "callback_url": callback_url
        }

        logger.info(f"发送IPv6配置到API: {api_url}")
        logger.info(f"发送的payload数据: config_id={config_obj.id}, VLAN={config_obj.vlan_id}, gateway={config_obj.gateway}")
        print(f"DEBUG IPv6配置API发送: config_id={config_obj.id}, VLAN={config_obj.vlan_id}, gateway={config_obj.gateway}")
        
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
        
        # 检查HTTP状态码
        api_success = (response.status_code == 200)
        
        logger.info(f"IPv6配置API响应: 状态码={response.status_code}, 数据={response_data}, 成功={api_success}")

        return {
            'success': api_success,
            'status_code': response.status_code,
            'response_data': response_data,
            'error': None
        }
        
    except requests.exceptions.Timeout:
        error_msg = "IPv6配置API请求超时（10秒）"
        logger.error(error_msg)
        return {
            'success': False,
            'status_code': None,
            'response_data': None,
            'error': error_msg
        }
        
    except requests.exceptions.ConnectionError:
        error_msg = "无法连接到IPv6配置API服务器"
        logger.error(error_msg)
        return {
            'success': False,
            'status_code': None,
            'response_data': None,
            'error': error_msg
        }
        
    except Exception as e:
        error_msg = f"发送IPv6配置API请求时出错: {str(e)}"
        logger.error(error_msg)
        return {
            'success': False,
            'status_code': None,
            'response_data': None,
            'error': error_msg
        }


def process_config_callback(callback_data):
    """
    处理IPv6配置的回调数据
    
    Args:
        callback_data (dict): 回调数据
        
    Returns:
        dict: 处理结果
        {
            'success': bool,
            'config_id': int,
            'message': str,
            'conflicts': list
        }
    """
    try:
        # 解析回调数据
        success_value = callback_data.get('success')
        config_id = callback_data.get('config_id')
        message = callback_data.get('message', '')
        conflicts = callback_data.get('conflicts', [])

        # 判断是否成功（支持多种格式）
        is_success = (
            success_value == 1 or success_value == '1' or
            success_value is True or success_value == 'true' or
            success_value == 'True' or success_value == True
        )

        # 验证config_id
        if not config_id:
            return {
                'success': False,
                'config_id': None,
                'message': '缺少必要参数：config_id',
                'conflicts': []
            }

        # 确保config_id是整数
        try:
            config_id = int(config_id)
        except (ValueError, TypeError):
            return {
                'success': False,
                'config_id': None,
                'message': 'config_id格式错误',
                'conflicts': []
            }

        return {
            'success': is_success,
            'config_id': config_id,
            'message': message,
            'conflicts': conflicts if isinstance(conflicts, list) else []
        }

    except Exception as e:
        logger.error(f"处理IPv6配置回调数据时出错: {str(e)}")
        return {
            'success': False,
            'config_id': None,
            'message': f'处理回调数据出错: {str(e)}',
            'conflicts': []
        }


def format_conflict_message(conflicts):
    """
    格式化冲突信息为用户友好的消息
    
    Args:
        conflicts (list): 冲突字段列表
        
    Returns:
        str: 格式化的冲突消息
    """
    if not conflicts:
        return "发送失败"
    
    field_mapping = {
        'vlan_id': '业务VLAN',
        'gateway': '业务网关',
        'dhcp_relay': 'DHCP服务器中继地址'
    }
    
    conflict_fields = []
    for conflict in conflicts:
        field_name = field_mapping.get(conflict, conflict)
        conflict_fields.append(field_name)
    
    return f"数据有冲突: {', '.join(conflict_fields)}"


# 常量定义
API_ENDPOINTS = {
    'KEA_ADD': 'http://222.204.3.179:3003/webhook/kea-add'
}

DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "IPv6-Config-System/1.0"
}

# 请求超时设置（秒）
REQUEST_TIMEOUT = 10
