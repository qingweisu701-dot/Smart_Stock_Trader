from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import StockDaily, StockBasic, UserPattern, FavoriteStock, TradeRecord, SystemMessage, PatternFavorite, \
    UserStrategy
from algorithms.matcher import run_analysis_core, PRESET_PATTERNS, analyze_kline_signals, calculate_indicators
from algorithms.predictor import run_lstm_prediction
from algorithms.backtest import run_backtest_strategy
import json, datetime
import pandas as pd
import numpy as np


# ==================== 页面渲染 ====================
def page_dashboard(request): return render(request, 'dashboard.html')


def page_pattern_lab(request): return render(request, 'pattern_lab.html')


def page_analysis_scan(request): return render(request, 'analysis_scan.html')


def page_analysis_fav(request): return render(request, 'analysis_fav.html')


def page_decision_center(request): return render(request, 'decision_center.html')


def page_trade_history(request): return render(request, 'trade_history.html')


def page_profit_analysis(request): return render(request, 'profit_analysis.html')


def page_pattern_draw(request): return render(request, 'pattern_lab.html')


# ==================== 核心 API ====================
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
            c = o * (1 + np.random.uniform(-0.02, 0.02))
            h = max(o, c) * 1.01;
            l = min(o, c) * 0.99;
            v = np.random.randint(1000, 5000)
            kline.append([d, round(o, 2), round(c, 2), round(l, 2), round(h, 2), v])
            curr = c

        last = kline[-1];
        prev = kline[-2]
        chg = (last[2] - prev[2]) / prev[2] * 100
        snap = {'name': '当前指数', 'price': last[2], 'change': f"{chg:.2f}%",
                'is_up': bool(change_pct > 0 if 'change_pct' in locals() else chg > 0), 'volume': f"{last[5] / 10}亿"}

        market = {'up_count': 2500, 'down_count': 1500, 'volume': '9000亿', 'hot_sector': '人工智能'}
        signals = [{'code': '600519.SH', 'name': '贵州茅台', 'pattern': '五浪上涨', 'change': 2.1}]

        return JsonResponse(
            {'code': 200, 'data': {'market': market, 'index_data': kline, 'signals': signals, 'snapshot': snap}})
    except Exception as e:
        return JsonResponse({'code': 500, 'msg': str(e)})


# 🔥 核心升级：消息推送与策略巡检接口
@csrf_exempt
def api_check_messages(request):
    try:
        # 1. 模拟后台策略巡检 (每当前端轮询时触发一次检查)
        strats = UserStrategy.objects.filter(is_monitoring=True)
        for s in strats:
            # 简单去重：如果最近有该策略的未读消息，就不重复发
            if not SystemMessage.objects.filter(title__contains=s.name, is_read=False).exists():
                # 模拟命中概率 30%
                if np.random.rand() > 0.7:
                    SystemMessage.objects.create(
                        title=f"🔔 策略命中: {s.name}",
                        content=f"您的策略【{s.name}】监控到符合条件的股票，建议关注。",
                        related_code="000001.SZ"
                    )

        # 2. 返回最新未读消息
        msgs = list(SystemMessage.objects.filter(is_read=False).order_by('-create_time').values()[:5])
        return JsonResponse({'code': 200, 'data': msgs})
    except Exception as e:
        return JsonResponse({'code': 200, 'data': []})


@csrf_exempt
def api_run_analysis(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            res = run_analysis_core(body.get('pattern_data'), body.get('filters', {}))
            for r in res:
                p = float(r['price'])
                r['buy_point'] = round(p * 0.98, 2);
                r['sell_point'] = round(p * 1.05, 2);
                r['holding_period'] = '5天'
            return JsonResponse({'code': 200, 'data': res})
        except:
            return JsonResponse({'code': 500})
    return JsonResponse({'code': 405})


@csrf_exempt
def api_stock_detail(request):
    """
    🔥 修复：安全获取指标，防止 KeyError 500 报错
    """
    try:
        code = request.GET.get('code', '000001.SZ')
        qs = StockDaily.objects.filter(ts_code=code).order_by('trade_date')

        # 即使没数据，也返回空结构，防止前端崩
        if not qs.exists():
            return JsonResponse({'code': 404, 'msg': '暂无数据'})

        data = list(qs.values('trade_date', 'open_price', 'close_price', 'low_price', 'high_price', 'vol'))
        df = pd.DataFrame(data)
        df.rename(columns={'open_price': 'open', 'close_price': 'close', 'high_price': 'high', 'low_price': 'low'},
                  inplace=True)

        # 计算指标
        df = calculate_indicators(df)
        signals = analyze_kline_signals(df)

        # 辅助函数：安全转 float list，确保列存在
        def sl(col_name):
            if col_name not in df.columns: return [0.0] * len(df)
            return [float(x) if not pd.isna(x) else 0.0 for x in df[col_name]]

        return JsonResponse({
            'code': 200,
            'data': {
                'dates': df['trade_date'].apply(lambda x: x.strftime('%Y-%m-%d')).tolist(),
                'values': df[['open', 'close', 'low', 'high', 'vol']].values.tolist(),  # OHLCV
                'indicators': {
                    'MA5': sl('MA5'), 'MA20': sl('MA20'),
                    'K': sl('K'), 'D': sl('D'), 'J': sl('J'),
                    'MACD': sl('MACD'), 'DIF': sl('DIF'), 'DEA': sl('DEA'),
                    'RSI': sl('RSI')
                },
                'signals': signals,
                'basic': {'pe': 20.5, 'industry': '半导体'},
                'funds': {'north_in': 5.2, 'main_in': -1.8, 'rzrq': '20亿'}
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'code': 500, 'msg': str(e)})


# ... (保持其他 API: save, list, toggle, fav, trade) ...
@csrf_exempt
def api_save_strategy(request):
    if request.method == 'POST':
        b = json.loads(request.body)
        UserStrategy.objects.create(name=b.get('name', '未命名'), criteria=b.get('filters', {}),
                                    is_monitoring=b.get('monitor', False))
        return JsonResponse({'code': 200})
    return JsonResponse({'code': 405})


def api_list_strategies(request): return JsonResponse({'code': 200, 'data': list(UserStrategy.objects.all().values())})


@csrf_exempt
def api_toggle_strategy_monitor(request):
    if request.method == 'POST': s = UserStrategy.objects.get(
        id=json.loads(request.body)['id']); s.is_monitoring = not s.is_monitoring; s.save(); return JsonResponse(
        {'code': 200, 'status': s.is_monitoring})
    return JsonResponse({'code': 405})


@csrf_exempt
def api_delete_strategy(request):
    if request.method == 'POST': UserStrategy.objects.filter(
        id=json.loads(request.body)['id']).delete(); return JsonResponse({'code': 200})


@csrf_exempt
def api_pattern_list(request):
    fav_qs = PatternFavorite.objects.all();
    fav_ids = set([f"{f.pattern_type}:{f.pattern_id}" for f in fav_qs])
    presets = [{'id': k, 'name': v['desc'], 'data': v['data'], 'type': v.get('signal', 'BUY'),
                'source_type': v.get('type', 'KLINE'), 'is_fav': f"PRESET:{k}" in fav_ids} for k, v in
               PRESET_PATTERNS.items()]
    users = [{'id': u.id, 'name': u.name, 'data': (
        json.loads(u.data_points) if u.source_type == 'KLINE' else [float(x) for x in u.data_points.split(',')]),
              'type': 'BUY', 'source_type': u.source_type, 'is_fav': f"USER:{u.id}" in fav_ids} for u in
             UserPattern.objects.all()]
    return JsonResponse({'code': 200, 'data': {'presets': presets, 'users': users}})


@csrf_exempt
def api_pattern_save(request): b = json.loads(request.body); d = json.dumps(b['data']) if b[
                                                                                              'type'] == 'KLINE' else ",".join(
    map(str, b['data'])); UserPattern.objects.create(name=b['name'], source_type=b['type'],
                                                     data_points=d); return JsonResponse({'code': 200})


@csrf_exempt
def api_pattern_delete(request): UserPattern.objects.filter(
    id=json.loads(request.body)['id']).delete(); return JsonResponse({'code': 200})


@csrf_exempt
def api_pattern_fav_toggle(request): b = json.loads(request.body); o, c = PatternFavorite.objects.get_or_create(
    pattern_id=str(b['id']), pattern_type=b.get('source_type', 'PRESET'));


if not c: o.delete(); return JsonResponse({'code': 200})


@csrf_exempt
def api_analyze_pattern_trend(request): return JsonResponse({'code': 200, 'data': {'trend': 'BUY'}})


@csrf_exempt
def api_pattern_quick_verify(request): return JsonResponse({'code': 200, 'data': {'count': 10, 'win_rate': 60}})


@csrf_exempt
def api_fav_add(request): FavoriteStock.objects.get_or_create(
    ts_code=json.loads(request.body)['code']); return JsonResponse({'code': 200})


def api_fav_list(request): return JsonResponse({'code': 200, 'data': list(FavoriteStock.objects.all().values())})


@csrf_exempt
def api_place_order(request): b = json.loads(request.body); TradeRecord.objects.create(ts_code=b['code'],
                                                                                       trade_date=datetime.date.today(),
                                                                                       trade_type=b['type'],
                                                                                       price=b['price'],
                                                                                       volume=b['volume'],
                                                                                       trigger_condition=b.get(
                                                                                           'triggerValue',
                                                                                           '')); return JsonResponse(
    {'code': 200})


def api_trade_data(request): return JsonResponse({'code': 200, 'data': list(TradeRecord.objects.all().values())})


@csrf_exempt
def api_run_prediction(request): return JsonResponse(
    {'code': 200, 'data': run_lstm_prediction(json.loads(request.body).get('code'))})


@csrf_exempt
def api_run_backtest(request): return JsonResponse(
    {'code': 200, 'data': run_backtest_strategy(json.loads(request.body).get('code'))})