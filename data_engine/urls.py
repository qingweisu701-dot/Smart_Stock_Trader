from django.urls import path
from . import views

urlpatterns = [
    # 1. 图形管理 (Pattern Lab)
    path('pattern/manage/', views.page_pattern_manage, name='page_pattern_manage'),
    path('pattern/list/', views.api_pattern_list, name='api_pattern_list'),
    path('pattern/save/', views.api_pattern_save, name='api_pattern_save'),

    # 2. 图形分析 (Analysis)
    path('analysis/', views.page_analysis, name='page_analysis'),
    path('analysis/run/', views.api_run_analysis, name='api_run_analysis'),
    path('favorite/toggle/', views.api_toggle_favorite, name='api_toggle_favorite'),
    path('favorite/list/', views.api_get_favorites, name='api_get_favorites'),

    # 3. 收益分析 (Prediction & Backtest)
    path('prediction/', views.page_prediction, name='page_prediction'),
    path('prediction/run/', views.api_run_prediction, name='api_run_prediction'),
    path('backtest/run/', views.api_run_backtest, name='api_run_backtest'),

    # 4. 交易记录
    path('trade/history/', views.page_trade_history, name='page_trade_history'),
    path('trade/data/', views.api_trade_data, name='api_trade_data'),
    path('trade/order/', views.api_place_order, name='api_place_order'),

    # 5. 通用数据
    path('kline/', views.api_get_kline, name='api_get_kline'),
]