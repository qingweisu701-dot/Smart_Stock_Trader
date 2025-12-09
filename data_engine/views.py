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


def page_profit_analysis(request): return render(request, 'profit_analysis.html')  # 🔥 新增


def page_analysis_fav(request): return render(request, 'analysis_fav.html')


def page_decision_center(request): return render(request, 'decision_center.html')


def page_trade_history(request): return render(request, 'trade_history.html')


def page_pattern_draw(request): return render(request, 'pattern_lab.html')


# ==================== 核心 API ====================
@csrf_exempt
def api_dashboard_data(request):
    try:
        index_type = request.GET.get('type', '000001.SH')
        base_price_map = {'000001.SH': 3200, '399001.SZ': 10500, '399006.SZ': 2100}
        base = base_price_map.get(index_type, 3000)

        dates = pd.date_range(end=datetime.date.today(), periods=100).strftime('%Y-%m-%d').tolist()
        kline = []
        curr = base
        for d in dates:
            o = curr;
            c = o * (1 + np.random.uniform(-0.02, 0.02));
            h = max(o, c) * 1.01;
            l = min(o, c) * 0.99;
            v = np.random.randint(1000, 5000)
            kline.append([d, round(o, 2), round(c, 2), round(l, 2), round(h, 2), v])
            curr = c

        market = {'up_count': 2500, 'down_count': 1500, 'volume': '9000亿', 'hot_sector': '半导体'}
        signals = [{'code': '600519.SH', 'name': '贵州茅台', 'pattern': '五浪上涨', 'change': 2.1}]

        last_c = kline[-1][2];
        prev_c = kline[-2][2]
        snapshot = {'name': '指数', 'price': last_c, 'change': f"{((last_c - prev_c) / prev_c * 100):.2f}%",
                    'is_up': last_c > prev_c, 'volume': '400亿'}

        return JsonResponse(
            {'code': 200, 'data': {'market': market, 'index_data': kline, 'signals': signals, 'snapshot': snapshot}})
    except Exception as e:
        return JsonResponse({'code': 500, 'msg': str(e)})


@csrf_exempt
def api_run_analysis(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            # 调用核心算法
            base_results = run_analysis_core(body.get('pattern_data'), body.get('filters', {}))

            # 🔥 增强：为结果添加【潜在买卖点】和【持仓周期】
            enhanced_results = []
            for r in base_results:
                curr_price = float(r['price'])
                # 模拟支撑压力位计算
                r['buy_point'] = round(curr_price * 0.98, 2)
                r['sell_point'] = round(curr_price * 1.05, 2)
                r['holding_period'] = f"{np.random.randint(3, 10)}天"  # 模拟周期
                enhanced_results.append(r)

            return JsonResponse({'code': 200, 'data': enhanced_results})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': str(e)})
    return JsonResponse({'code': 405})


# ==================== 策略管理 API (新增) ====================
@csrf_exempt
def api_save_strategy(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            UserStrategy.objects.create(
                name=body.get('name', '未命名'),
                criteria=body.get('filters', {}),
                is_monitoring=body.get('monitor', False)
            )
            return JsonResponse({'code': 200, 'msg': '策略已保存'})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': str(e)})
    return JsonResponse({'code': 405})


def api_list_strategies(request):
    return JsonResponse({'code': 200, 'data': list(UserStrategy.objects.all().values())})


@csrf_exempt
def api_toggle_strategy_monitor(request):
    if request.method == 'POST':
        s = UserStrategy.objects.get(id=json.loads(request.body)['id'])
        s.is_monitoring = not s.is_monitoring
        s.save()
        return JsonResponse({'code': 200, 'status': s.is_monitoring})
    return JsonResponse({'code': 405})


# ==================== 其他必要 API (保持不变) ====================
@csrf_exempt
def api_pattern_list(request):
    fav_qs = PatternFavorite.objects.all();
    fav_ids = set([f"{f.pattern_type}:{f.pattern_id}" for f in fav_qs])
    presets = [{'id': k, 'name': v['desc'], 'data': v['data'], 'type': v.get('signal', 'BUY'),
                'source_type': v.get('type', 'KLINE'), 'is_fav': f"PRESET:{k}" in fav_ids} for k, v in
               PRESET_PATTERNS.items()]
    users = []
    for u in UserPattern.objects.all():
        data = json.loads(u.data_points) if u.source_type == 'KLINE' else [float(x) for x in u.data_points.split(',')]
        is_fav = f"USER:{u.id}" in fav_ids
        users.append(
            {'id': u.id, 'name': u.name, 'data': data, 'type': 'BUY', 'source_type': u.source_type, 'is_fav': is_fav})
    return JsonResponse({'code': 200, 'data': {'presets': presets, 'users': users}})


@csrf_exempt
def api_stock_detail(request):
    code = request.GET.get('code', '000001.SZ')
    qs = StockDaily.objects.filter(ts_code=code).order_by('trade_date')
    if not qs.exists(): return JsonResponse({'code': 404})
    data = list(qs.values('trade_date', 'open_price', 'close_price', 'low_price', 'high_price', 'vol'))
    df = pd.DataFrame(data);
    df.rename(columns={'open_price': 'open', 'close_price': 'close', 'high_price': 'high', 'low_price': 'low'},
              inplace=True)
    df = calculate_indicators(df);
    signals = analyze_kline_signals(df)

    def sl(s): return [float(x) if not pd.isna(x) else 0 for x in s]

    return JsonResponse({'code': 200, 'data': {
        'dates': df['trade_date'].apply(lambda x: x.strftime('%Y-%m-%d')).tolist(),
        'values': df[['open', 'close', 'low', 'high', 'vol']].values.tolist(),
        'indicators': {'MA5': sl(df['MA5']), 'MA20': sl(df['MA20']), 'K': sl(df['K']), 'D': sl(df['D']),
                       'J': sl(df['J'])},
        'signals': signals, 'basic': {'pe': 20, 'pb': 2, 'total_mv': '100亿'}, 'funds': {'north_in': 5, 'main_in': -2}
    }})


# ... (其余 pattern_save, delete, toggle, fav_add, trade, predict, backtest, check_msg 等) ...
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
def api_pattern_quick_verify(request): return JsonResponse(
    {'code': 200, 'data': {'count': 10, 'win_rate': 70, 'avg_return': 5}})


@csrf_exempt
def api_fav_add(request): FavoriteStock.objects.get_or_create(
    ts_code=json.loads(request.body)['code']); return JsonResponse({'code': 200})


def api_fav_list(request): return JsonResponse({'code': 200,
                                                'data': [{'code': f.ts_code, 'name': f.ts_code, 'group': f.group} for f
                                                         in FavoriteStock.objects.all()]})


@csrf_exempt
def api_place_order(request): b = json.loads(request.body); TradeRecord.objects.create(ts_code=b['code'],
                                                                                       trade_date=datetime.date.today(),
                                                                                       trade_type=b['type'],
                                                                                       price=b['price'], volume=b[
        'volume']); return JsonResponse({'code': 200})


def api_trade_data(request): return JsonResponse({'code': 200, 'data': list(TradeRecord.objects.all().values())})


@csrf_exempt
def api_run_prediction(request): return JsonResponse(
    {'code': 200, 'data': run_lstm_prediction(json.loads(request.body).get('code'))})


@csrf_exempt
def api_run_backtest(request): return JsonResponse(
    {'code': 200, 'data': run_backtest_strategy(json.loads(request.body).get('code'))})


def api_check_messages(request): return JsonResponse({'code': 200, 'data': []})