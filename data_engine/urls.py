from django.urls import path
from . import views

urlpatterns = [
    # API 接口 (给代码用的)
    path('kline/', views.get_kline_data, name='get_kline_data'),
    # 页面入口 (给用户看的) -> 访问地址: /api/chart/
    path('chart/', views.kline_page, name='kline_page'),
    path('match/', views.match_pattern, name='match_pattern'),
    path('order/', views.place_order, name='place_order'),
    path('prediction/', views.prediction_page, name='prediction_page'),
    path('prediction/run/', views.get_prediction, name='get_prediction'),
]