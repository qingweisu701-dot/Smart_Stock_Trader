from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

def redirect_to_home(request):
    """
    根目录重定向函数：
    当访问 http://127.0.0.1:8000/ 时，
    自动跳转到新的【市场智能扫描】页面
    """
    # 🔴 修复点：从 '/api/analysis/' 更新为 '/api/analysis/scan/'
    return redirect('/api/analysis/scan/')

urlpatterns = [
    path('admin/', admin.site.urls),

    # 挂载你的应用路由
    path('api/', include('data_engine.urls')),

    # 根路径自动跳转
    path('', redirect_to_home),
]