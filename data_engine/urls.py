from django.urls import path
from . import views

urlpatterns = [
    # 1. 图形管理
    path('pattern/lab/', views.page_pattern_lab, name='page_pattern'),
    path('pattern/list/', views.api_pattern_list, name='api_pattern_list'),
    path('pattern/save/', views.api_pattern_save, name='api_pattern_save'),
    path('pattern/delete/', views.api_pattern_delete, name='api_pattern_delete'),
    path('pattern/analyze/', views.api_analyze_pattern_trend, name='api_analyze_pattern_trend'),
    # [新增] 形态收藏接口
    path('pattern/fav/toggle/', views.api_pattern_fav_toggle, name='api_pattern_fav_toggle'),

    # 2. 市场扫描
    path('analysis/scan/', views.page_analysis_scan, name='page_analysis_scan'),
    path('analysis/fav/', views.page_analysis_fav, name='page_analysis_fav'),
    path('analysis/run/', views.api_run_analysis, name='api_run_analysis'),
    path('stock/detail/', views.api_stock_detail, name='api_stock_detail'),

    # 3. 决策与交易
    path('prediction/run/', views.api_run_prediction, name='api_run_prediction'),
    path('backtest/run/', views.api_run_backtest, name='api_run_backtest'),
    path('decision/center/', views.page_decision_center, name='page_decision_center'),

    path('trade/history/', views.page_trade_history, name='page_trade'),
    path('trade/order/', views.api_place_order, name='api_place_order'),
    path('trade/data/', views.api_trade_data, name='api_trade_data'),

    # 4. 通用
    path('favorite/add/', views.api_fav_add, name='api_fav_add'),
    path('favorite/list/', views.api_fav_list, name='api_fav_list'),
    path('message/check/', views.api_check_messages, name='api_check_messages'),
]