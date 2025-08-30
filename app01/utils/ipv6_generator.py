import ipaddress


def generate_ipv6(department: int, building: int, service: int, mac: str) -> str:
    """
    根据部门、楼栋、业务类型编号和 MAC 生成 IPv6 地址
    前缀64位固定为 240c:c901:a:a
    部门4位、楼栋8位、业务类型4位、最后mac48位
    
    Args:
        department: 部门编号 (0-15)
        building: 楼栋编号 (0-255) 
        service: 业务类型编号 (0-15)
        mac: MAC地址 (格式: XX:XX:XX:XX:XX:XX)
        
    Returns:
        str: 生成的IPv6地址
        
    Raises:
        ValueError: 参数范围错误或MAC地址格式错误
    """
    # 前缀（64位）
    prefix = "240c:c901:a:a"
    
    # 校验范围
    if not (0 <= department < 16):
        raise ValueError("部门编号必须在 0-15 范围内")
    if not (0 <= building < 256):
        raise ValueError("楼栋编号必须在 0-255 范围内")
    if not (0 <= service < 16):
        raise ValueError("业务类型编号必须在 0-15 范围内")
    
    # 转换成二进制并拼接 (部门4b + 楼栋8b + 业务4b)
    dept_bin = f"{department:04b}"
    build_bin = f"{building:08b}"
    service_bin = f"{service:04b}"
    extra_bits = dept_bin + build_bin + service_bin  # 一共16位
    
    # 转成十六进制
    extra_hex = f"{int(extra_bits, 2):04x}"
    
    # MAC 转换成十六进制字符串（去掉冒号）
    mac_hex = mac.replace(":", "").lower()
    if len(mac_hex) != 12:
        raise ValueError("MAC 地址格式错误，应为 12 个十六进制字符")
    
    # 拼接完整 IPv6
    ipv6 = f"{prefix}:{extra_hex}:{mac_hex[0:4]}:{mac_hex[4:8]}:{mac_hex[8:12]}"
    
    # 压缩标准 IPv6 表示
    return str(ipaddress.IPv6Address(ipv6))


def validate_mac_address(mac: str) -> bool:
    """
    验证MAC地址格式是否正确
    
    Args:
        mac: MAC地址字符串
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not mac:
        return False
        
    # 移除所有分隔符并转换为小写
    clean_mac = mac.replace(":", "").replace("-", "").lower()
    
    # 检查长度和字符
    if len(clean_mac) != 12:
        return False
        
    try:
        int(clean_mac, 16)
        return True
    except ValueError:
        return False
