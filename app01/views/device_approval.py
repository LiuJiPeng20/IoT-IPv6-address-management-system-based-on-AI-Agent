from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Max
from app01 import models
from app01.utils.pagination import Pagination
from app01.utils.form import DeviceApprovalModelForm

def device_approval_list(request):
    """ 设备审批列表 """
    # 根据用户身份判断是否启用搜索功能
    admin_info = request.session.get("info")
    user_info = request.session.get("user_info")

    # 构造搜索 - 只对普通用户启用搜索功能
    data_dict = {}
    search_data = ""
    
    if user_info:  # 只有普通用户才能搜索
        search_data = request.GET.get('q', "")
        if search_data:
            # 用户只能通过DUID或MAC搜索（使用OR逻辑）
            from django.db.models import Q
            data_dict = Q(duid__contains=search_data) | Q(mac_address__contains=search_data)

    if data_dict:
        queryset = models.DeviceApproval.objects.filter(data_dict).order_by('-id')
    else:
        queryset = models.DeviceApproval.objects.all().order_by('-id')
    
    page_object = Pagination(request, queryset, page_size=10)
    context = {
        "search_data": search_data,
        "queryset": page_object.page_queryset,
        "page_string": page_object.html(),
    }

    print(f"DEBUG in device_approval_list: admin_info={admin_info}, user_info={user_info}") # DEBUG

    if admin_info:
        return render(request, 'device_approval_admin_list.html', context)
    elif user_info:
        return render(request, 'device_approval_list.html', context)
    else:
        return redirect('/login/') # 如果未登录，重定向到登录页面

def device_approval_add(request):
    """ 添加设备审批请求 """
    if request.method == "GET":
        form = DeviceApprovalModelForm(
            initial={'user': request.session['user_info']['name'], 'status': 2}
        )
        return render(request, 'change.html', {"form": form, "title": "提交设备审批"})
    
    form = DeviceApprovalModelForm(data=request.POST)
    if form.is_valid():
        # 由于 user 和 status 是 disabled 的，它们不会出现在 request.POST 中，需要手动设置
        form.instance.user = request.session['user_info']['name']
        form.instance.status = 2  # 始终设置为审批中
        form.save()
        return redirect('/device/approval/list/')
    return render(request, 'change.html', {"form": form, "title": "提交设备审批"})

def device_approval_edit(request, nid):
    """ 编辑设备审批请求 """
    row_object = models.DeviceApproval.objects.filter(id=nid).first()
    if not row_object:
        return redirect('/device/approval/list/')

    if request.method == "GET":
        form = DeviceApprovalModelForm(instance=row_object)
        return render(request, 'change.html', {"form": form, "title": "编辑设备审批"})

    form = DeviceApprovalModelForm(data=request.POST, instance=row_object)
    if form.is_valid():
        # 由于 user 和 status 是 disabled 的，它们不会出现在 request.POST 中，需要手动设置
        form.instance.user = row_object.user # 保持原始用户，如果需要允许修改则从session获取
        form.instance.status = row_object.status # 保持原始状态，只有管理员才能修改
        form.save()
        return redirect('/device/approval/list/')
    return render(request, 'change.html', {"form": form, "title": "编辑设备审批"})

def device_approval_delete(request, nid):
    """ 删除设备审批请求 """
    try:
        device_approval_obj = models.DeviceApproval.objects.filter(id=nid).first()
        if not device_approval_obj:
            messages.error(request, "审批记录不存在")
            return redirect('/device/approval/list/')

        # 获取审批信息用于提示
        approval_info = f"用户: {device_approval_obj.user}, 部门: {device_approval_obj.department.title}"
        
        # 删除审批记录
        device_approval_obj.delete()
        
        messages.success(request, f"设备审批记录删除成功！({approval_info})")
        
    except Exception as e:
        messages.error(request, f"删除审批记录失败：{str(e)}")
    
    return redirect('/device/approval/list/')

def device_approval_approve(request, nid):
    """ 同意设备审批 - 自动生成IPv6并发送到API """
    # 权限检查
    if not request.session.get("info"):
        return redirect('/login/') # 非管理员重定向到登录页

    device_approval_obj = models.DeviceApproval.objects.filter(id=nid).first()
    if not device_approval_obj:
        messages.error(request, "审批记录不存在")
        return redirect('/device/approval/list/')

    if request.method == "POST":
        try:
            # 1. 生成IPv6地址
            from app01.utils.ipv6_generator import generate_ipv6

            department_id = device_approval_obj.department.id
            building_id = device_approval_obj.building
            business_type_id = device_approval_obj.business_type
            mac_address = device_approval_obj.mac_address

            generated_ipv6 = generate_ipv6(
                department=department_id,
                building=building_id,
                service=business_type_id,
                mac=mac_address
            )

            # 2. 检查是否已存在相同MAC地址的记录（避免重复创建）
            existing_ipv6 = models.PrettyNum.objects.filter(mac_address=device_approval_obj.mac_address).first()

            if existing_ipv6:
                # 如果已存在相同MAC地址的记录，使用现有记录
                ipv6_obj = existing_ipv6
                print(f"DEBUG: 发现已存在的IPv6记录，ID={ipv6_obj.id}, 复用该记录")
                # 更新现有记录的信息
                ipv6_obj.user = device_approval_obj.user
                ipv6_obj.ipv6_address = generated_ipv6
                ipv6_obj.department = device_approval_obj.department
                ipv6_obj.building = device_approval_obj.building
                ipv6_obj.send_status = 'pending'
                ipv6_obj.save()
            else:
                # 创建新的IPv6记录
                ipv6_obj = models.PrettyNum.objects.create(
                    user=device_approval_obj.user,
                    ipv6_address=generated_ipv6,
                    mac_address=device_approval_obj.mac_address,
                    department=device_approval_obj.department,  # 添加部门信息
                    building=device_approval_obj.building,     # 添加楼栋信息
                    send_status='pending'  # 等待API回调确认绑定结果
                )
                print(f"DEBUG: 创建新的IPv6记录，ID={ipv6_obj.id}")

            # 强制保存并刷新对象，确保数据库中存在记录
            ipv6_obj.refresh_from_db()
            print(f"DEBUG: IPv6记录已创建，ID={ipv6_obj.id}, IPv6={ipv6_obj.ipv6_address}")

            # 验证IPv6记录确实存在于数据库中
            check_ipv6 = models.PrettyNum.objects.filter(id=ipv6_obj.id).first()
            if not check_ipv6:
                raise Exception(f"IPv6记录创建失败，ID={ipv6_obj.id}在数据库中不存在")

            # 3. 发送IPv6到API - 使用IPv6记录的ID作为record_id
            from app01.utils.ipv6_api import send_to_kea_api

            # 构建回调URL
            callback_url = request.build_absolute_uri('/api/kea/callback/')

            print(f"DEBUG: 准备发送到API，record_id={ipv6_obj.id}, IPv6={generated_ipv6}")
            print(f"DEBUG: 当前数据库中最大的IPv6记录ID: {models.PrettyNum.objects.all().aggregate(max_id=Max('id'))['max_id']}")
            print(f"DEBUG: 当前所有IPv6记录: {list(models.PrettyNum.objects.values_list('id', 'ipv6_address', 'mac_address')[:10])}")

            result = send_to_kea_api(
                record_id=ipv6_obj.id,  # 使用IPv6记录ID作为标识，这样回调时能正确找到
                ipv6_address=generated_ipv6,
                mac_address=device_approval_obj.mac_address,
                duid=device_approval_obj.duid,  # 直接传递DUID参数
                callback_url=callback_url
            )

            print(f"DEBUG: API发送结果: {result}")

            # 检查HTTP发送是否成功（200状态码表示请求成功发送）
            if result.get('status_code') == 200:
                # 4. 创建设备记录 - HTTP发送成功就创建设备
                models.Device.objects.create(
                    user=device_approval_obj.user,
                    create_time=timezone.now(),
                    department=device_approval_obj.department,
                    building=device_approval_obj.building,
                    business_type=device_approval_obj.business_type,
                    duid=device_approval_obj.duid,
                    mac_address=device_approval_obj.mac_address,
                )

                # 5. 更新审批状态
                device_approval_obj.status = 1  # 设置状态为同意
                device_approval_obj.save()

                messages.success(request, f"设备审批已同意！IPv6地址 {generated_ipv6} 已生成并发送到API，正在等待绑定确认...")
            else:
                # HTTP发送失败 - 删除已创建的IPv6记录
                ipv6_obj.delete()
                error_msg = result.get('error', f"API返回失败状态码: {result.get('status_code', 'Unknown')}")
                messages.error(request, f"设备审批同意失败！IPv6发送到API时出错: {error_msg}")

        except Exception as e:
            messages.error(request, f"处理设备审批时出现异常：{str(e)}")

    return redirect('/device/approval/list/')

def device_approval_reject(request, nid):
    """ 拒绝设备审批 """
    # 权限检查
    if not request.session.get("info"):
        return redirect('/login/') # 非管理员重定向到登录页

    device_approval_obj = models.DeviceApproval.objects.filter(id=nid).first()
    if not device_approval_obj:
        return render(request, 'error.html', {"msg": "审批记录不存在"})

    if request.method == "POST":
        device_approval_obj.status = 0  # 设置状态为不同意
        device_approval_obj.save()
        return redirect('/device/approval/list/')
    return redirect('/device/approval/list/')


from django.utils import timezone
