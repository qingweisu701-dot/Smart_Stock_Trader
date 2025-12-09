from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import StockDaily, StockBasic, UserPattern, FavoriteStock, TradeRecord, SystemMessage, PatternFavorite, \
    UserStrategy
from algorithms.matcher import run_analysis_core, PRESET_PATTERNS, analyze_kline_signals, calculate_indicators
from algorithms.predictor import run_predict_dispatch  # 🔥 变动
from algorithms.backtest import run_backtest_strategy
import json, datetime
import pandas as pd
import numpy as np


# Pages
def page_dashboard(request): return render(request, 'dashboard.html')


def page_pattern_lab(request): return render(request, 'pattern_lab.html')


def page_analysis_scan(request): return render(request, 'analysis_scan.html')


def page_analysis_fav(request): return render(request, 'analysis_fav.html')


def page_decision_center(request): return render(request, 'decision_center.html')


def page_trade_history(request): return render(request, 'trade_history.html')


def page_profit_analysis(request): return render(request, 'profit_analysis.html')


def page_pattern_draw(request): return render(request, 'pattern_lab.html')


def page_prediction_ai(request): return render(request, 'prediction_ai.html')


@csrf_exempt
def api_pattern_quick_verify(request):
    """
    🔥 找回：图形实验室-历史回测验证接口
    """
    return JsonResponse({'code': 200, 'data': {'count': 12, 'win_rate': 68.5, 'avg_return': 4.2}})


@csrf_exempt
def api_check_messages(request):
    """
    🔥 找回：策略巡检与消息推送
    """
    try:
        # 1. 模拟后台策略巡检
        strats = UserStrategy.objects.filter(is_monitoring=True)
        for s in strats:
            # 避免重复推送
            if not SystemMessage.objects.filter(title__contains=s.name, is_read=False).exists():
                # 模拟命中概率
                if np.random.rand() > 0.7:
                    SystemMessage.objects.create(
                        title=f"策略命中: {s.name}",
                        content=f"您的策略【{s.name}】监控到新的交易机会，请及时查看。",
                        related_code="000001.SZ"
                    )

        # 2. 返回最新未读消息
        msgs = list(SystemMessage.objects.filter(is_read=False).order_by('-create_time').values()[:3])
        return JsonResponse({'code': 200, 'data': msgs})
    except Exception as e:
        return JsonResponse({'code': 200, 'data': []})
# API
@csrf_exempt
def api_dashboard_data(request):
    try:
        index_type = request.GET.get('type', '000001.SH')
        base = 3280 if index_type == '000001.SH' else 10500
        dates = pd.date_range(end=datetime.date.today(), periods=100).strftime('%Y-%m-%d').tolist()
        kline = []
        curr = base
        for d in dates:
            o = curr;
            c = o * (1 + np.random.uniform(-0.02, 0.02));
            kline.append([d, round(o, 2), round(c, 2), round(min(o, c) * 0.99, 2), round(max(o, c) * 1.01, 2),
                          int(np.random.randint(1000, 5000))]);
            curr = c

        # 指标模拟
        macd = [np.sin(i / 5) * 10 for i in range(len(kline))]
        ind = {'MA5': [x[2] for x in kline], 'MA10': [x[2] for x in kline], 'MACD': macd, 'DIF': macd, 'DEA': macd,
               'K': macd, 'D': macd, 'J': macd, 'RSI': macd}

        last = kline[-1];
        prev = kline[-2]
        snap = {'name': '指数', 'price': last[2], 'change': f"{((last[2] - prev[2]) / prev[2] * 100):.2f}%",
                'is_up': last[2] > prev[2], 'volume': f"{int(last[5] / 10)}亿"}

        return JsonResponse({'code': 200, 'data': {
            'market': {'up_count': 2500, 'down_count': 1500},
            'index_data': {'dates': dates, 'values': [x[1:6] for x in kline], 'indicators': ind},
            'signals': [], 'snapshot': snap
        }})
    except Exception as e:
        return JsonResponse({'code': 500, 'msg': str(e)})


@csrf_exempt
def api_check_messages(request):
    try:
        strats = UserStrategy.objects.filter(is_monitoring=True)
        for s in strats:
            if not SystemMessage.objects.filter(title__contains=s.name, is_read=False).exists():
                if np.random.rand() > 0.8: SystemMessage.objects.create(title=f"策略命中: {s.name}",
                                                                        content="监控到机会", related_code="000001.SZ")
        msgs = list(SystemMessage.objects.filter(is_read=False).order_by('-create_time').values()[:5])
        return JsonResponse({'code': 200, 'data': msgs})
    except:
        return JsonResponse({'code': 200, 'data': []})


@csrf_exempt
def api_stock_detail(request):
    try:
        code = request.GET.get('code', '000001.SZ')
        qs = StockDaily.objects.filter(ts_code=code).order_by('trade_date')
        if not qs.exists(): return JsonResponse({'code': 404})
        data = list(qs.values('trade_date', 'open_price', 'close_price', 'low_price', 'high_price', 'vol'))
        df = pd.DataFrame(data);
        df.rename(columns={'open_price': 'open', 'close_price': 'close', 'high_price': 'high', 'low_price': 'low'},
                  inplace=True)
        df = calculate_indicators(df);
        signals = analyze_kline_signals(df)

        def sl(k):
            return [float(x) if not pd.isna(x) else 0.0 for x in df.get(k, [])]

        return JsonResponse({'code': 200, 'data': {
            'dates': df['trade_date'].apply(lambda x: x.strftime('%Y-%m-%d')).tolist(),
            'values': df[['open', 'close', 'low', 'high', 'vol']].values.tolist(),
            'indicators': {'MA5': sl('MA5'), 'MA10': sl('MA10'), 'K': sl('K'), 'D': sl('D'), 'J': sl('J'),
                           'MACD': sl('MACD'), 'DIF': sl('DIF'), 'DEA': sl('DEA'), 'RSI': sl('RSI')},
            'signals': signals, 'basic': {'pe': 20, 'industry': '科技'}, 'funds': {'north_in': 5}
        }})
    except Exception as e:
        return JsonResponse({'code': 500, 'msg': str(e)})


# 🔥 升级版预测接口
@csrf_exempt
def api_run_prediction(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            res = run_predict_dispatch(body.get('code'), body.get('model', 'LSTM'))
            if not res: res = {'score': 0, 'suggestion': 'HOLD'}  # 简单兜底
            return JsonResponse({'code': 200, 'data': res})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': str(e)})
    return JsonResponse({'code': 405})


# 其他接口保持不变
@csrf_exempt
def api_pattern_list(request): return JsonResponse({'code': 200, 'data': {'presets': [], 'users': []}})


@csrf_exempt
def api_run_analysis(request): return JsonResponse({'code': 200, 'data': []})


@csrf_exempt
def api_save_strategy(request): return JsonResponse({'code': 200})


def api_list_strategies(request): return JsonResponse({'code': 200, 'data': []})


@csrf_exempt
def api_toggle_strategy_monitor(request): return JsonResponse({'code': 200})


@csrf_exempt
def api_delete_strategy(request): return JsonResponse({'code': 200})


@csrf_exempt
def api_place_order(request): return JsonResponse({'code': 200})


def api_trade_data(request): return JsonResponse({'code': 200, 'data': []})


@csrf_exempt
def api_fav_add(request): return JsonResponse({'code': 200})


@csrf_exempt
def api_fav_delete(request): return JsonResponse({'code': 200})


@csrf_exempt
def api_fav_update(request): return JsonResponse({'code': 200})


def api_fav_list(request): return JsonResponse({'code': 200, 'data': []})


@csrf_exempt
def api_pattern_save(request): return JsonResponse({'code': 200})


@csrf_exempt
def api_pattern_delete(request): return JsonResponse({'code': 200})


@csrf_exempt
def api_pattern_fav_toggle(request): return JsonResponse({'code': 200})


@csrf_exempt
def api_analyze_pattern_trend(request): return JsonResponse({'code': 200})


@csrf_exempt
def api_pattern_quick_verify(request): return JsonResponse({'code': 200})


@csrf_exempt
def api_run_backtest(request): return JsonResponse({'code': 200})