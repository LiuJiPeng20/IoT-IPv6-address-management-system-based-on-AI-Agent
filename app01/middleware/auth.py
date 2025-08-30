from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import HttpResponse, redirect


class AuthMiddleware(MiddlewareMixin):

    def process_request(self, request):
        # 0.排除那些不需要登录就能访问的页面
        if request.path_info in ["/login/", "/image/code/", "/api/kea/callback/", "/api/kea/test/"]:
            return

        # 1.读取当前访问的用户的session信息，如果能读到，说明已登陆过，就可以继续向后走。
        admin_info = request.session.get("info")
        user_info = request.session.get("user_info")

        if admin_info or user_info:
            # 如果需要更细粒度的权限控制，例如管理员只能访问管理员页面，用户只能访问用户页面，
            # 可以在这里添加更多逻辑。目前，只要任一身份登录，就允许访问，
            # 具体跳转到哪个首页由login视图决定。
            return

        # 2.没有登录过，重新回到登录页面
        return redirect('/login/')
