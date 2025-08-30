from django.shortcuts import render, HttpResponse, redirect
from django import forms
from io import BytesIO

from app01.utils.code import check_code
from app01 import models
from app01.utils.bootstrap import BootStrapForm
from app01.utils.encrypt import md5
from app01.utils.form import CombinedLoginForm # 导入 CombinedLoginForm

# LoginForm 将被 CombinedLoginForm 替代，因此删除
# class LoginForm(BootStrapForm):
#     username = forms.CharField(
#         label="用户名",
#         widget=forms.TextInput,
#         required=True
#     )
#     password = forms.CharField(
#         label="密码",
#         widget=forms.PasswordInput(render_value=True),
#         required=True
#     )
#     code = forms.CharField(
#         label="验证码",
#         widget=forms.TextInput,
#         required=True
#     )
#     def clean_password(self):
#         pwd = self.cleaned_data.get("password")
#         return md5(pwd)

def login(request):
    """ 统一登录入口 """
    if request.method == "GET":
        form = CombinedLoginForm()
        return render(request, 'login.html', {'form': form})

    form = CombinedLoginForm(data=request.POST)
    if form.is_valid():
        # 验证码的校验
        user_input_code = form.cleaned_data.pop('code')
        code = request.session.get('image_code', "")
        if code.upper() != user_input_code.upper():
            form.add_error("code", "验证码错误")
            return render(request, 'login.html', {'form': form})

        # 身份和用户对象已在 form 的 clean 方法中处理
        identity = form.cleaned_data.get('identity')
        user_object = form.user_object

        if identity == 'admin':
            request.session.pop('user_info', None) # 清除用户会话信息
            request.session["info"] = {'id': user_object.id, 'name': user_object.username}
            request.session.set_expiry(60 * 60 * 24 * 7)
            return redirect("/admin/list/")
        elif identity == 'user':
            request.session.pop('info', None) # 清除管理员会话信息
            request.session["user_info"] = {'id': user_object.id, 'name': user_object.name}
            request.session.set_expiry(60 * 60 * 24 * 7)
            return redirect("/device/approval/list/")
    # else:
        # print("Form is not valid.")
        # print(form.errors)

    return render(request, 'login.html', {'form': form})

# user_login 函数不再需要，因为已合并到 login
# def user_login(request):
#     """ 用户登录 """
#     if request.method == "GET":
#         form = UserLoginForm()
#         return render(request, 'user_login.html', {'form': form})
#
#     form = UserLoginForm(data=request.POST)
#     if form.is_valid():
#         user_object = form.instance
#         request.session["user_info"] = {'id': user_object.id, 'name': user_object.name}
#         request.session.set_expiry(60 * 60 * 24 * 7)
#         return redirect("/device/approval/list/")
#
#     return render(request, 'user_login.html', {'form': form})

def image_code(request):
    """ 生成图片验证码 """
    img, code_string = check_code()
    request.session['image_code'] = code_string
    request.session.set_expiry(60)
    stream = BytesIO()
    img.save(stream, 'png')
    return HttpResponse(stream.getvalue())

def logout(request):
    """ 注销 """
    request.session.pop('info', None) # 尝试移除管理员session
    request.session.pop('user_info', None) # 尝试移除用户session
    request.session.clear() # 清除所有剩余session数据（以防万一）
    return redirect('/login/')
