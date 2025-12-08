from django.urls import path
from . import views

urlpatterns = [
    # 1. 图形实验室 (拆分)
    path('pattern/draw/', views.page_pattern_draw, name='page_pattern_draw'),   # 独立手绘
    path('pattern/build/', views.page_pattern_build, name='page_pattern_build'), # 独立构造
    path('pattern/list/', views.api_pattern_list, name='api_pattern_list'),
    path('pattern/save/', views.api_pattern_save, name='api_pattern_save'),
    path('pattern/analyze/', views.api_analyze_pattern_trend, name='api_analyze_pattern_trend'),

    # 2. 市场扫描 (拆分)
    path('analysis/scan/', views.page_analysis_scan, name='page_analysis_scan'),
    path('analysis/fav/', views.page_analysis_fav, name='page_analysis_fav'),
    path('analysis/run/', views.api_run_analysis, name='api_run_analysis'),
    path('stock/detail/', views.api_stock_detail, name='api_stock_detail'),

    # 3. 量化决策 (拆分)
    path('prediction/ai/', views.page_prediction_ai, name='page_prediction_ai'),         # 独立AI
    path('prediction/backtest/', views.page_prediction_backtest, name='page_prediction_backtest'), # 独立回测
    path('prediction/run/', views.api_run_prediction, name='api_run_prediction'),
    path('backtest/run/', views.api_run_backtest, name='api_run_backtest'),

    # 4. 交易中心
    path('trade/history/', views.page_trade_history, name='page_trade_history'),
    path('trade/order/', views.api_place_order, name='api_place_order'),
    path('trade/data/', views.api_trade_data, name='api_trade_data'),

    # 5. 通用
    path('favorite/add/', views.api_fav_add, name='api_fav_add'),
    path('favorite/list/', views.api_fav_list, name='api_fav_list'),
    path('message/check/', views.api_check_messages, name='api_check_messages'),
]