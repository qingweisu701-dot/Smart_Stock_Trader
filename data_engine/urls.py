from django.urls import path
from . import views

urlpatterns = [
    # 1. 图形管理 (Pattern Lab)
    path('pattern/draw/', views.page_pattern_draw, name='page_pattern_draw'),  # 绘制页面
    path('pattern/list_page/', views.page_pattern_list, name='page_pattern_list'),  # 【新】模板清单页面

    path('pattern/list/', views.api_pattern_list, name='api_pattern_list'),  # 数据接口
    path('pattern/save/', views.api_pattern_save, name='api_pattern_save'),
    path('pattern/analyze/', views.api_analyze_pattern_trend, name='api_analyze_pattern_trend'),
    path('pattern/delete/', views.api_pattern_delete, name='api_pattern_delete'),

    # 2. 市场分析
    path('analysis/scan/', views.page_analysis_scan, name='page_analysis_scan'),  # 筛选器
    path('analysis/fav/', views.page_analysis_fav, name='page_analysis_fav'),  # 收藏夹
    path('analysis/run/', views.api_run_analysis, name='api_run_analysis'),
    path('stock/detail/', views.api_stock_detail, name='api_stock_detail'),

    # 3. 收藏与交易
    path('favorite/add/', views.api_fav_add, name='api_fav_add'),
    path('favorite/list/', views.api_fav_list, name='api_fav_list'),
    path('trade/order/', views.api_place_order, name='api_place_order'),
    path('trade/history/', views.page_trade_history, name='page_trade'),
    path('trade/data/', views.api_trade_data, name='api_trade_data'),

    # 4. 预测与消息
    path('prediction/', views.page_prediction, name='page_prediction'),
    path('prediction/run/', views.api_run_prediction, name='api_run_prediction'),
    path('backtest/run/', views.api_run_backtest, name='api_run_backtest'),
    path('message/check/', views.api_check_messages, name='api_check_messages'),

    # 5. 旧接口兼容
    path('kline/', views.get_kline_data, name='get_kline_data'),
]