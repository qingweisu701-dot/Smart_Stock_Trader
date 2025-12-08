from django.urls import path
from . import views

urlpatterns = [
    # 1. 图形管理
    path('pattern/manage/', views.page_pattern_manage, name='page_pattern'),
    path('pattern/list/', views.api_pattern_list, name='api_pattern_list'),
    path('pattern/save/', views.api_pattern_save, name='api_pattern_save'),

    # 2. 市场分析
    path('analysis/', views.page_analysis, name='page_analysis'),
    path('analysis/run/', views.api_run_analysis, name='api_run_analysis'),
    path('stock/detail/', views.api_stock_detail, name='api_stock_detail'), # 详情页数据

    # 3. 收藏与交易
    path('favorite/add/', views.api_fav_add, name='api_fav_add'),
    path('favorite/list/', views.api_fav_list, name='api_fav_list'),
    path('trade/order/', views.api_place_order, name='api_place_order'),
    path('trade/history/', views.page_trade_history, name='page_trade'),
    path('trade/data/', views.api_trade_data, name='api_trade_data'),

    # 4. 预测与消息
    path('prediction/', views.page_prediction, name='page_prediction'),
    path('message/check/', views.api_check_messages, name='api_check_messages'), # 轮询消息
]