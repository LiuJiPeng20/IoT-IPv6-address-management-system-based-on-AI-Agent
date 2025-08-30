from app01 import models
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django import forms
from app01.utils.bootstrap import BootStrapModelForm
from app01.utils.encrypt import md5 # 导入 md5 函数


class UserModelForm(BootStrapModelForm):
    name = forms.CharField(
        min_length=3,
        label="用户名",
        widget=forms.TextInput(attrs={"class": "form-control"})
    )

    class Meta:
        model = models.UserInfo
        fields = ["name", "password", "create_time","depart"]

# 验证方式 (统一登录表单)
class CombinedLoginForm(forms.Form):
    username = forms.CharField(
        label="用户名",
        widget=forms.TextInput(attrs={"class": "form-control"}),
        required=True
    )
    password = forms.CharField(
        label="密码",
        widget=forms.PasswordInput(attrs={"class": "form-control", "render_value": True}),
        required=True
    )
    code = forms.CharField(
        label="验证码",
        widget=forms.TextInput(attrs={"class": "form-control"}),
        required=True
    )
    # 身份选择字段
    identity_choices = (
        ('admin', '管理员'),
        ('user', '用户'),
    )
    identity = forms.ChoiceField(
        label="登录身份",
        choices=identity_choices,
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
        initial='admin',
        required=True
    )

    # 移除 __init__ 方法和 _password_from_clean_password 属性

    def clean_password(self):
        pwd = self.cleaned_data.get("password")
        return pwd # clean_password 不再进行加密，直接返回原始密码

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password = cleaned_data.get('password') # 此时获取的是原始密码
        identity = cleaned_data.get('identity')

        if not username or not password or not identity:
            return cleaned_data # 让各自字段的错误显示

        password_to_check = password
        if identity == 'admin':
            password_to_check = md5(password) # 对管理员密码进行MD5加密
            admin_object = models.Admin.objects.filter(username=username, password=password_to_check).first()
            if not admin_object:
                raise ValidationError("管理员用户名或密码错误")
            self.user_object = admin_object
        elif identity == 'user':
            user_object = models.UserInfo.objects.filter(name=username, password=password_to_check).first()
            if not user_object:
                raise ValidationError("用户用户名或密码错误")
            self.user_object = user_object

        # 关键：将加密后的密码更新到 cleaned_data 中，以便后续视图函数使用
        if identity == 'admin':
            cleaned_data['password'] = password_to_check

        return cleaned_data


class PrettyModelForm(BootStrapModelForm):
    class Meta:
        model = models.PrettyNum
        fields = ["ipv6_address", "user", "mac_address"]

    def clean_ipv6_address(self):
        txt_ipv6_address = self.cleaned_data["ipv6_address"]
        exists = models.PrettyNum.objects.filter(ipv6_address=txt_ipv6_address).exists()
        if exists:
            raise ValidationError("IPv6地址已存在")
        return txt_ipv6_address


class PrettyEditModelForm(BootStrapModelForm):
    class Meta:
        model = models.PrettyNum
        fields = ['ipv6_address', "user", "mac_address"]

    def clean_ipv6_address(self):
        txt_ipv6_address = self.cleaned_data["ipv6_address"]
        exists = models.PrettyNum.objects.exclude(id=self.instance.pk).filter(ipv6_address=txt_ipv6_address).exists()
        if exists:
            raise ValidationError("IPv6地址已存在")
        return txt_ipv6_address


class DeviceModelForm(BootStrapModelForm):
    class Meta:
        model = models.Device
        # 管理员只读，不能编辑
        fields = "__all__"
        widgets = {
            'user': forms.TextInput(attrs={'disabled': True}),
            'create_time': forms.DateTimeInput(attrs={'disabled': True}),
            'department': forms.Select(attrs={'disabled': True}),
            'building': forms.Select(attrs={'disabled': True}),
            'business_type': forms.Select(attrs={'disabled': True}),
            'duid': forms.TextInput(attrs={'disabled': True}),
            'mac_address': forms.TextInput(attrs={'disabled': True}),
        }


class DeviceApprovalModelForm(BootStrapModelForm):
    # 重新定义用户字段，设置为disabled
    user = forms.CharField(label="用户", disabled=True, required=False)
    
    # 自定义DUID和MAC地址字段，添加placeholder提示
    duid = forms.CharField(
        label="DUID", 
        max_length=64, 
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '00:01:00:01:2B:6F:B5:91:00:00:00:00:00:00',
            'class': 'form-control'
        })
    )
    
    mac_address = forms.CharField(
        label="设备MAC", 
        max_length=17, 
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': '00:00:00:00:00:00',
            'class': 'form-control'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 在BootStrap处理完成后，重新设置我们想要的placeholder
        self.fields['duid'].widget.attrs['placeholder'] = '格式：00:01:00:01:2B:6F:B5:91:00:00:00:00:00:00'
        self.fields['mac_address'].widget.attrs['placeholder'] = '格式：00:00:00:00:00:00'

    class Meta:
        model = models.DeviceApproval
        # 指定字段顺序：用户、业务类型、部门、楼栋、DUID、MAC地址
        # 删除status字段，用户填写时不需要看到
        fields = ["user", "business_type", "department", "building", "duid", "mac_address"]


class IPv6ConfigModelForm(BootStrapModelForm):
    """ IPv6地址配置表单 """
    
    admin_name = forms.CharField(
        label="管理员名",
        max_length=32,
        widget=forms.TextInput(attrs={
            'placeholder': '操作的管理员用户名',
            'class': 'form-control'
        })
    )
    
    vlan_id = forms.IntegerField(
        label="业务VLAN",
        widget=forms.NumberInput(attrs={
            'placeholder': 'VLAN范围在2-4094',
            'class': 'form-control',
            'min': 2,
            'max': 4094
        })
    )
    
    gateway = forms.CharField(
        label="业务网关",
        max_length=64,
        widget=forms.TextInput(attrs={
            'placeholder': '例如：240C:C901:A:A::1/64',
            'class': 'form-control'
        })
    )
    
    dhcp_relay = forms.CharField(
        label="DHCP服务器中继地址",
        max_length=64,
        widget=forms.TextInput(attrs={
            'placeholder': '例如：2001:250:6c00:3:8241:26ff:fe5f:ee2e',
            'class': 'form-control'
        })
    )

    class Meta:
        model = models.IPv6Config
        fields = ["admin_name", "vlan_id", "gateway", "dhcp_relay"]

    def clean_vlan_id(self):
        """ 校验VLAN范围 """
        vlan_id = self.cleaned_data.get('vlan_id')
        if vlan_id is None:
            raise ValidationError("VLAN不能为空")
        if not (2 <= vlan_id <= 4094):
            raise ValidationError("请输入正确的VLAN(2-4094)")
        return vlan_id

    def clean_gateway(self):
        """ 校验业务网关格式 """
        gateway = self.cleaned_data.get('gateway')
        if not gateway:
            raise ValidationError("业务网关不能为空")
        
        # 检查是否以::1/64结尾
        if not gateway.endswith('::1/64'):
            raise ValidationError("格式错误请重新输入")
        
        # 基本的IPv6格式检查
        try:
            # 移除/64后缀进行IPv6格式检查
            ipv6_part = gateway.replace('/64', '')
            import ipaddress
            ipaddress.IPv6Address(ipv6_part)
        except:
            raise ValidationError("格式错误请重新输入")
        
        return gateway


class IPv6ConfigEditModelForm(IPv6ConfigModelForm):
    """ IPv6地址配置编辑表单 """
    
    class Meta:
        model = models.IPv6Config
        fields = ["admin_name", "vlan_id", "gateway", "dhcp_relay"]

    def clean_vlan_id(self):
        """ 校验VLAN范围，编辑时排除自身 """
        vlan_id = self.cleaned_data.get('vlan_id')
        if vlan_id is None:
            raise ValidationError("VLAN不能为空")
        if not (2 <= vlan_id <= 4094):
            raise ValidationError("请输入正确的VLAN(2-4094)")
        
        # 检查VLAN是否重复（排除自身）
        existing = models.IPv6Config.objects.filter(vlan_id=vlan_id)
        if self.instance and self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise ValidationError(f"VLAN {vlan_id} 已存在")
        
        return vlan_id
