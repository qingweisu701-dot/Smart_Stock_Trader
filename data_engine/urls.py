from django.urls import path
from . import views

urlpatterns = [
    # 0. 首页
    path('dashboard/', views.page_dashboard, name='page_dashboard'),
    path('dashboard/data/', views.api_dashboard_data, name='api_dashboard_data'),

    # 1. 图形管理
    path('pattern/lab/', views.page_pattern_lab, name='page_pattern_lab'),
    path('pattern/list/', views.api_pattern_list, name='api_pattern_list'),
    path('pattern/save/', views.api_pattern_save, name='api_pattern_save'),
    path('pattern/delete/', views.api_pattern_delete, name='api_pattern_delete'),
    path('pattern/analyze/', views.api_analyze_pattern_trend, name='api_analyze_pattern_trend'),
    path('pattern/fav/toggle/', views.api_pattern_fav_toggle, name='api_pattern_fav_toggle'),
    path('pattern/verify/', views.api_pattern_quick_verify, name='api_pattern_quick_verify'),

    # 2. 市场分析 (升级)
    path('analysis/scan/', views.page_analysis_scan, name='page_analysis_scan'),
    path('analysis/profit/', views.page_profit_analysis, name='page_profit_analysis'),  # 🔥 新增：收益分析
    path('analysis/run/', views.api_run_analysis, name='api_run_analysis'),
    path('analysis/fav/', views.page_analysis_fav, name='page_analysis_fav'),

    # 🔥 新增：策略管理
    path('strategy/save/', views.api_save_strategy, name='api_save_strategy'),
    path('strategy/list/', views.api_list_strategies, name='api_list_strategies'),
    path('strategy/toggle_monitor/', views.api_toggle_strategy_monitor, name='api_toggle_strategy_monitor'),

    # 3. 决策
    path('decision/center/', views.page_decision_center, name='page_decision_center'),
    path('stock/detail/', views.api_stock_detail, name='api_stock_detail'),
    path('prediction/run/', views.api_run_prediction, name='api_run_prediction'),
    path('backtest/run/', views.api_run_backtest, name='api_run_backtest'),

    # 4. 交易与通用
    path('trade/history/', views.page_trade_history, name='page_trade_history'),
    path('trade/order/', views.api_place_order, name='api_place_order'),
    path('trade/data/', views.api_trade_data, name='api_trade_data'),
    path('favorite/add/', views.api_fav_add, name='api_fav_add'),
    path('favorite/list/', views.api_fav_list, name='api_fav_list'),
    path('message/check/', views.api_check_messages, name='api_check_messages'),
    path('kline/', views.api_stock_detail),
]