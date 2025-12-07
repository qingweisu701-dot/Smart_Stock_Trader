from django.urls import path
from . import views

urlpatterns = [
    # 1. K线图页面与数据
    path('chart/', views.kline_page, name='kline_page'),
    path('kline/', views.get_kline_data, name='get_kline_data'),

    # 2. 核心匹配与下单
    path('match/', views.match_pattern, name='match_pattern'),
    path('order/', views.place_order, name='place_order'),

    # 3. 历史回测
    path('history/', views.history_page, name='history_page'),
    path('history/data/', views.get_trade_history, name='get_trade_history'),

    # 4. 预测中心
    path('prediction/', views.prediction_page, name='prediction_page'),
    path('prediction/run/', views.get_prediction, name='get_prediction'),
]