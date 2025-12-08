from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

def redirect_to_home(request):
    """
    根目录重定向函数：
    当访问 http://127.0.0.1:8000/ 时，
    自动跳转到新的【市场扫描与分析】页面
    """
    # 🔴 修改点：从 '/api/chart/' 改为 '/api/analysis/'
    return redirect('/api/analysis/')

urlpatterns = [
    path('admin/', admin.site.urls),

    # 挂载你的应用路由
    path('api/', include('data_engine.urls')),

    # 根路径自动跳转
    path('', redirect_to_home),
]