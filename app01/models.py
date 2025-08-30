from django.db import models


# Shared choices (moved from Device and DeviceApproval for reusability)
BUILDING_CHOICES = []
for i in range(1, 31):
    BUILDING_CHOICES.append((i, f"{i}栋"))

BUSINESS_TYPE_CHOICES = []
for i in range(1, 6):
    BUSINESS_TYPE_CHOICES.append((i, f"物联网设备0{i}"))

class Admin(models.Model):
    """ 管理员 """
    username = models.CharField(verbose_name="用户名", max_length=32)
    password = models.CharField(verbose_name="密码", max_length=64)

    def __str__(self):
        return self.username

class Department(models.Model):
    """ 部门表 """
    title = models.CharField(verbose_name='标题', max_length=32)

    def __str__(self):
        return self.title


class UserInfo(models.Model):
    """ 用户表 """
    name = models.CharField(verbose_name="姓名", max_length=16)
    password = models.CharField(verbose_name="密码", max_length=64)
    create_time = models.DateTimeField(verbose_name="注册时间")  # 自动记录注册时间
    # account = models.DecimalField(verbose_name="账户余额", max_digits=10, decimal_places=2, default=0)
    # create_time = models.DateTimeField(verbose_name="入职时间")
    # create_time = models.DateField(verbose_name="入职时间")v   

    depart = models.ForeignKey(verbose_name="部门", to="Department", to_field="id", on_delete=models.CASCADE)
    # ### 3.2 置空
    # depart = models.ForeignKey(to="Department", to_field="id", null=True, blank=True, on_delete=models.SET_NULL)

    # 在django中做的约束
    #gender_choices = (
    #    (1, "男"),
    #    (2, "女"),
    #)
    #gender = models.SmallIntegerField(verbose_name="性别", choices=gender_choices)
    def __str__(self):
        return self.name


class PrettyNum(models.Model):
    """ IPv6地址绑定表 """
    user = models.CharField(verbose_name="用户", max_length=32)
    ipv6_address = models.CharField(verbose_name="IPv6地址", max_length=45, unique=True)
    mac_address = models.CharField(verbose_name="MAC地址", max_length=17, null=True, blank=True)

    # 添加部门和楼栋字段，从设备审批表继承
    department = models.ForeignKey(verbose_name="部门", to="Department", on_delete=models.CASCADE, null=True, blank=True)
    building = models.SmallIntegerField(verbose_name="楼栋", choices=BUILDING_CHOICES, default=1, null=True, blank=True)

    # API状态相关字段
    SEND_STATUS_CHOICES = [
        ('pending', '待发送'),
        ('bound', '绑定成功'),
        ('failed', '发送失败'),
        ('bind_failed', '绑定失败'),
        ('retrying', '重试中'),
    ]
    send_status = models.CharField(verbose_name="绑定状态", max_length=15, choices=SEND_STATUS_CHOICES, default='pending')
    last_send_time = models.DateTimeField(verbose_name="最后发送时间", null=True, blank=True)
    retry_count = models.IntegerField(verbose_name="重试次数", default=0)
    next_retry_time = models.DateTimeField(verbose_name="下次重试时间", null=True, blank=True)
    api_response = models.TextField(verbose_name="API响应", null=True, blank=True)

    def __str__(self):
        return self.ipv6_address
    
    def get_error_message(self):
        """获取绑定失败时的错误消息"""
        if self.send_status == 'bind_failed' and self.api_response:
            try:
                import json
                data = json.loads(self.api_response)
                return data.get('error_message', '未知错误')
            except:
                return '解析错误信息失败'
        return None


class Device(models.Model):
    """ 设备表 """
    user = models.CharField(verbose_name="用户", max_length=32)

    # 修改为审批时间，并移除 auto_now_add
    create_time = models.DateTimeField(verbose_name="审批时间")
    department = models.ForeignKey(verbose_name="部门", to="Department", on_delete=models.CASCADE)

    # 引用全局常量
    building = models.SmallIntegerField(verbose_name="楼栋", choices=BUILDING_CHOICES, default=1)
    
    # 引用全局常量
    business_type = models.SmallIntegerField(verbose_name="业务类型", choices=BUSINESS_TYPE_CHOICES, default=1)
    
    duid = models.CharField(verbose_name="DUID", max_length=64, unique=True, null=True, blank=True)
    mac_address = models.CharField(verbose_name="设备MAC", max_length=17, unique=True, null=True, blank=True)
    
    # 设备状态字段
    STATUS_CHOICES = [
        ('online', '在线'),
        ('offline', '已下线'),
    ]
    status = models.CharField(verbose_name="设备状态", max_length=10, choices=STATUS_CHOICES, default='online')
    
    def __str__(self):
        return f"{self.building} - {self.mac_address}"


class DeviceApproval(models.Model):
    """ 设备审批表 """
    user = models.CharField(verbose_name="用户", max_length=32)
    department = models.ForeignKey(verbose_name="部门", to="Department", on_delete=models.CASCADE)

    # 引用全局常量
    building = models.SmallIntegerField(verbose_name="楼栋", choices=BUILDING_CHOICES, default=1)

    # 引用全局常量
    business_type = models.SmallIntegerField(verbose_name="业务类型", choices=BUSINESS_TYPE_CHOICES, default=1)

    duid = models.CharField(verbose_name="DUID", max_length=64, null=True, blank=True)
    mac_address = models.CharField(verbose_name="设备MAC", max_length=17, null=True, blank=True)

    status_choices = (
        (0, "不同意"),
        (1, "同意"),
        (2, "审批中"),
    )
    status = models.SmallIntegerField(verbose_name="状态", choices=status_choices, default=2)

    def __str__(self):
        # 修改 __str__ 方法以反映 department 字段
        return f"{self.user} - {self.department.title} - {self.building}栋"


class IPv6Config(models.Model):
    """ IPv6地址配置表 """
    admin_name = models.CharField(verbose_name="管理员名", max_length=32)
    vlan_id = models.IntegerField(verbose_name="业务VLAN", help_text="VLAN范围在2-4094")
    gateway = models.CharField(verbose_name="业务网关", max_length=64, help_text="例如：240C:C901:A:A::1/64")
    dhcp_relay = models.CharField(verbose_name="DHCP服务器中继地址", max_length=64, help_text="例如：2001:250:6c00:3:8241:26ff:fe5f:ee2e")
    
    # 发送状态
    SEND_STATUS_CHOICES = [
        ('pending', '待发送'),
        ('sent', '已发送'),
        ('success', '发送成功'),
        ('failed', '发送失败'),
    ]
    send_status = models.CharField(verbose_name="发送状态", max_length=10, choices=SEND_STATUS_CHOICES, default='pending')
    
    create_time = models.DateTimeField(verbose_name="创建时间", auto_now_add=True)
    update_time = models.DateTimeField(verbose_name="更新时间", auto_now=True)
    
    # API响应信息
    api_response = models.TextField(verbose_name="API响应", null=True, blank=True)
    
    def __str__(self):
        return f"VLAN{self.vlan_id} - {self.admin_name}"

