"""day16 URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path

from app01.views import depart, user, pretty, admin, account, device_approval, device, ipv6_config # 导入视图

urlpatterns = [
    # path('admin/', admin.site.urls),

    # 部门管理
    path('depart/list/', depart.depart_list),
    path('depart/add/', depart.depart_add),
    path('depart/delete/', depart.depart_delete),
    path('depart/<int:nid>/edit/', depart.depart_edit),

    # 用户管理
    path('user/list/', user.user_list),
#    path('user/add/', user.user_add),
    path('user/model/form/add/', user.user_model_form_add),
    path('user/<int:nid>/edit/', user.user_edit),
    path('user/<int:nid>/delete/', user.user_delete),

    # IPv6地址绑定管理
    path('pretty/list/', pretty.pretty_list),
    path('pretty/<int:nid>/send/', pretty.send_ipv6_address),
    path('pretty/<int:nid>/delete/', pretty.pretty_delete),
    path('api/kea/callback/', pretty.kea_callback, name='kea_callback'),  # KEA API回调URL
    path('api/kea/test/', pretty.kea_callback_test, name='kea_callback_test'),  # 回调测试端点
    path('api/device/offline/callback/', pretty.device_offline_callback, name='device_offline_callback'),  # 设备下线回调URL

    # 管理员的管理
    path('admin/list/', admin.admin_list),
    path('admin/add/', admin.admin_add),
    path('admin/<int:nid>/edit/', admin.admin_edit),
    path('admin/<int:nid>/delete/', admin.admin_delete),
    path('admin/<int:nid>/reset/', admin.admin_reset),

    # 登录
    path('login/', account.login),
    path('logout/', account.logout),
    path('image/code/', account.image_code),

    # 用户登录 (此路由已合并到 /login/ 中，因此删除)
    # path('user/login/', account.user_login),

    # 设备管理
    path('device/list/', device.device_list),
    path('device/<int:nid>/offline/', device.device_offline),

    # 设备审批管理
    path('device/approval/list/', device_approval.device_approval_list),
    path('device/approval/add/', device_approval.device_approval_add),
    path('device/approval/<int:nid>/edit/', device_approval.device_approval_edit),
    path('device/approval/<int:nid>/delete/', device_approval.device_approval_delete),
    path('device/approval/<int:nid>/approve/', device_approval.device_approval_approve),
    path('device/approval/<int:nid>/reject/', device_approval.device_approval_reject),

    # IPv6地址配置管理
    path('ipv6/config/list/', ipv6_config.ipv6_config_list),
    path('ipv6/config/add/', ipv6_config.ipv6_config_add),
    path('ipv6/config/<int:nid>/edit/', ipv6_config.ipv6_config_edit),
    path('ipv6/config/<int:nid>/send/', ipv6_config.ipv6_config_send),
    path('api/ipv6/config/callback/', ipv6_config.ipv6_config_callback, name='ipv6_config_callback'),
]
