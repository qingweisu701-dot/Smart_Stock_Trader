from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import StockDaily, StockBasic, UserPattern, FavoriteStock, TradeRecord, SystemMessage, PatternFavorite
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


def page_pattern_draw(request): return render(request, 'pattern_lab.html')


# ==================== 核心 API ====================
@csrf_exempt
def api_dashboard_data(request):
    """首页数据接口"""
    try:
        index_type = request.GET.get('type', '000001.SH')
        configs = {
            '000001.SH': {'name': '上证指数', 'base': 3285, 'vol': 4000},
            '399001.SZ': {'name': '深证成指', 'base': 10500, 'vol': 5000},
            '399006.SZ': {'name': '创业板指', 'base': 2150, 'vol': 2000},
            '000300.SH': {'name': '沪深300', 'base': 3850, 'vol': 3000},
            '000688.SH': {'name': '科创50', 'base': 980, 'vol': 1000},
        }
        cfg = configs.get(index_type, configs['000001.SH'])

        dates = pd.date_range(end=datetime.date.today(), periods=100).strftime('%Y-%m-%d').tolist()
        df_sim = pd.DataFrame(index=dates, columns=['open', 'close', 'high', 'low', 'vol'])
        curr_p = cfg['base']
        for d in dates:
            chg = np.random.normal(0, 0.015)
            c = curr_p * (1 + chg)
            o = curr_p
            h = max(o, c) * 1.01
            l = min(o, c) * 0.99
            v = np.random.randint(100000, 500000)
            df_sim.loc[d] = [float(o), float(c), float(h), float(l), int(v)]
            curr_p = c

        df_sim = calculate_indicators(df_sim)

        kline_data = []
        for date, row in df_sim.iterrows():
            kline_data.append([
                str(date), float(round(row['open'], 2)), float(round(row['close'], 2)),
                float(round(row['low'], 2)), float(round(row['high'], 2)), int(row['vol']),
                float(round(row.get('MACD', 0), 3)), float(round(row.get('DIF', 0), 3)),
                float(round(row.get('DEA', 0), 3)),
                float(round(row.get('K', 0), 2)), float(round(row.get('D', 0), 2)), float(round(row.get('J', 0), 2)),
                float(round(row.get('RSI', 0), 2))
            ])

        last_close = float(df_sim.iloc[-1]['close'])
        prev_close = float(df_sim.iloc[-2]['close'])
        pct_chg = (last_close - prev_close) / prev_close * 100

        snapshot = {
            'name': cfg['name'], 'price': f"{last_close:.2f}",
            'change': f"{pct_chg:+.2f}%", 'is_up': bool(pct_chg > 0),
            'volume': f"{int(df_sim.iloc[-1]['vol'] / 10000)}亿"
        }
        market = {'up_count': int(np.random.randint(2000, 3000)), 'down_count': int(np.random.randint(1000, 2000)),
                  'volume': snapshot['volume'], 'hot_sector': '人工智能'}
        signals = [{'code': '600519.SH', 'name': '贵州茅台', 'pattern': '五浪上涨', 'change': 2.1}]

        return JsonResponse({'code': 200, 'data': {'snapshot': snapshot, 'market': market, 'index_data': kline_data,
                                                   'signals': signals}})
    except Exception as e:
        return JsonResponse({'code': 500, 'msg': str(e)})


@csrf_exempt
def api_stock_detail(request):
    code = request.GET.get('code', '000001.SZ')
    qs = StockDaily.objects.filter(ts_code=code).order_by('trade_date')
    if not qs.exists(): return JsonResponse({'code': 404, 'msg': '无数据'})

    data = list(qs.values('trade_date', 'open_price', 'close_price', 'low_price', 'high_price', 'vol'))
    df = pd.DataFrame(data)
    df.rename(columns={'open_price': 'open', 'close_price': 'close', 'high_price': 'high', 'low_price': 'low'},
              inplace=True)
    df = calculate_indicators(df)
    signals = analyze_kline_signals(df)

    def safe_list(s): return [float(x) if not pd.isna(x) else 0.0 for x in s]

    return JsonResponse({
        'code': 200,
        'data': {
            'dates': df['trade_date'].apply(lambda x: x.strftime('%Y-%m-%d')).tolist(),
            'values': df[['open', 'close', 'low', 'high', 'vol']].values.tolist(),
            'indicators': {
                'MA5': safe_list(df['MA5']), 'MA20': safe_list(df['MA20']),
                'K': safe_list(df['K']), 'D': safe_list(df['D']), 'J': safe_list(df['J']),
                'MACD': safe_list(df['MACD']), 'DIF': safe_list(df['DIF']), 'DEA': safe_list(df['DEA']),
                'RSI': safe_list(df['RSI'])
            },
            'signals': signals,
            'basic': {'pe': 25.5, 'pb': 2.1, 'total_mv': '1500亿', 'industry': '银行'},
            'funds': {'north_in': 5.2, 'main_in': -1.8, 'rzrq': '20亿'}
        }
    })


# 🔥 【找回功能】形态快速历史验证
@csrf_exempt
def api_pattern_quick_verify(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            # 复用 matcher 核心，但只跑少量数据做演示
            results = run_analysis_core(body.get('data'), {'minScore': 75})
            count = len(results)
            # 简单模拟胜率 (真实项目应根据日期回测后5日涨跌)
            win_rate = 60 + (count % 30)
            return JsonResponse({'code': 200, 'data': {
                'count': count,
                'win_rate': win_rate,
                'avg_return': round((win_rate - 50) * 0.5, 2)
            }})
        except:
            return JsonResponse({'code': 200, 'data': {'count': 0, 'win_rate': 0, 'avg_return': 0}})
    return JsonResponse({'code': 405})


# ... (保持 api_pattern_list, save, etc. 不变) ...
@csrf_exempt
def api_pattern_list(request):
    try:
        fav_qs = PatternFavorite.objects.all()
        fav_ids = set([f"{f.pattern_type}:{f.pattern_id}" for f in fav_qs])
        presets = [{'id': k, 'name': v['desc'], 'data': v['data'], 'type': v.get('signal', 'BUY'),
                    'source_type': v.get('type', 'KLINE'), 'is_fav': f"PRESET:{k}" in fav_ids} for k, v in
                   PRESET_PATTERNS.items()]
        users = []
        for u in UserPattern.objects.all():
            try:
                data = json.loads(u.data_points) if u.source_type == 'KLINE' else [float(x) for x in
                                                                                   u.data_points.split(',')]
                is_fav = f"USER:{u.id}" in fav_ids
                signal = 'BUY' if 'BUY' in u.description else 'SELL'
                users.append({'id': u.id, 'name': u.name, 'data': data, 'type': signal, 'source_type': u.source_type,
                              'is_fav': is_fav})
            except:
                pass
        return JsonResponse({'code': 200, 'data': {'presets': presets, 'users': users}})
    except:
        return JsonResponse({'code': 200, 'data': {'presets': [], 'users': []}})


@csrf_exempt
def api_pattern_save(request):
    if request.method == 'POST':
        b = json.loads(request.body)
        d = json.dumps(b['data']) if b['type'] == 'KLINE' else ",".join(map(str, b['data']))
        UserPattern.objects.create(name=b['name'], source_type=b['type'], description=b.get('desc', ''), data_points=d)
        return JsonResponse({'code': 200})
    return JsonResponse({'code': 405})


@csrf_exempt
def api_pattern_fav_toggle(request):
    if request.method == 'POST':
        b = json.loads(request.body);
        pid = str(b['id']);
        ptype = b.get('source_type', 'PRESET')
        if ptype == 'CUSTOM': ptype = 'USER'
        o, c = PatternFavorite.objects.get_or_create(pattern_id=pid, pattern_type=ptype)
        if not c: o.delete()
        return JsonResponse({'code': 200, 'status': c})


@csrf_exempt
def api_run_analysis(request):
    if request.method == 'POST':
        body = json.loads(request.body)
        res = run_analysis_core(body.get('pattern_data'), body.get('filters', {}))
        return JsonResponse({'code': 200, 'data': res})
    return JsonResponse({'code': 405})


@csrf_exempt
def api_analyze_pattern_trend(request): return JsonResponse({'code': 200, 'data': {'trend': 'BUY'}})


@csrf_exempt
def api_pattern_delete(request):
    if request.method == 'POST': UserPattern.objects.filter(
        id=json.loads(request.body)['id']).delete(); return JsonResponse({'code': 200})


@csrf_exempt
def api_fav_add(request):
    if request.method == 'POST': FavoriteStock.objects.get_or_create(
        ts_code=json.loads(request.body)['code']); return JsonResponse({'code': 200})


def api_fav_list(request): return JsonResponse({'code': 200, 'data': []})


@csrf_exempt
def api_place_order(request): return JsonResponse({'code': 200})


def api_trade_data(request): return JsonResponse({'code': 200, 'data': []})


@csrf_exempt
def api_run_prediction(request): return JsonResponse(
    {'code': 200, 'data': run_lstm_prediction(json.loads(request.body).get('code'))})


@csrf_exempt
def api_run_backtest(request): return JsonResponse(
    {'code': 200, 'data': run_backtest_strategy(json.loads(request.body).get('code'))})


def api_check_messages(request): return JsonResponse({'code': 200, 'data': []})