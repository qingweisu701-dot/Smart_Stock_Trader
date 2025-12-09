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


# ==================== Page Views ====================
def page_dashboard(request): return render(request, 'dashboard.html')


def page_pattern_lab(request): return render(request, 'pattern_lab.html')


def page_analysis_scan(request): return render(request, 'analysis_scan.html')


def page_analysis_fav(request): return render(request, 'analysis_fav.html')


def page_decision_center(request): return render(request, 'decision_center.html')


def page_trade_history(request): return render(request, 'trade_history.html')


def page_profit_analysis(request): return render(request, 'profit_analysis.html')


def page_pattern_draw(request): return render(request, 'pattern_lab.html')


# ==================== Dashboard API (核心修复) ====================
@csrf_exempt
def api_dashboard_data(request):
    try:
        index_type = request.GET.get('type', '000001.SH')
        base = 3280 if index_type == '000001.SH' else 10500
        dates = pd.date_range(end=datetime.date.today(), periods=100).strftime('%Y-%m-%d').tolist()
        kline = []
        curr = base

        # 生成模拟K线
        for d in dates:
            o = curr
            c = o * (1 + np.random.uniform(-0.02, 0.02))
            h = max(o, c) * 1.01
            l = min(o, c) * 0.99
            v = np.random.randint(1000, 5000)
            # 🔥 强制转换所有数值为 Python 原生类型
            kline.append([
                str(d),
                float(round(o, 2)),
                float(round(c, 2)),
                float(round(l, 2)),
                float(round(h, 2)),
                int(v)
            ])
            curr = c

        # 计算快照
        last = kline[-1]
        prev = kline[-2]
        chg = (last[2] - prev[2]) / prev[2] * 100

        snapshot = {
            'name': '当前指数',
            'price': float(last[2]),
            'change': f"{chg:.2f}%",
            'is_up': bool(chg > 0),  # 🔥 强制转换为 Python bool
            'volume': f"{int(last[5] / 10)}亿"
        }

        # 强制转换 numpy.int32 为 int
        market = {
            'up_count': int(np.random.randint(2000, 3000)),
            'down_count': int(np.random.randint(1000, 2000)),
            'volume': '8800亿',
            'hot_sector': '人工智能'
        }

        signals = [
            {'code': '600519.SH', 'name': '贵州茅台', 'pattern': '五浪上涨', 'change': 2.1},
            {'code': '300750.SZ', 'name': '宁德时代', 'pattern': 'MACD金叉', 'change': 1.5}
        ]

        return JsonResponse({
            'code': 200,
            'data': {
                'market': market,
                'index_data': kline,
                'signals': signals,
                'snapshot': snapshot
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'code': 500, 'msg': str(e)})


@csrf_exempt
def api_check_messages(request):
    try:
        strats = UserStrategy.objects.filter(is_monitoring=True)
        for s in strats:
            if not SystemMessage.objects.filter(title__contains=s.name, is_read=False).exists():
                if np.random.rand() > 0.7:
                    SystemMessage.objects.create(
                        title=f"策略命中: {s.name}",
                        content=f"您的策略【{s.name}】监控到交易机会，请查看。",
                        related_code="000001.SZ"
                    )
        msgs = list(SystemMessage.objects.filter(is_read=False).order_by('-create_time').values()[:5])
        return JsonResponse({'code': 200, 'data': msgs})
    except:
        return JsonResponse({'code': 200, 'data': []})


# ==================== Pattern API ====================
@csrf_exempt
def api_pattern_list(request):
    try:
        fav_qs = PatternFavorite.objects.all()
        fav_ids = set([f"{f.pattern_type}:{f.pattern_id}" for f in fav_qs])

        presets = []
        for k, v in PRESET_PATTERNS.items():
            is_fav = f"PRESET:{k}" in fav_ids
            presets.append({
                'id': k, 'name': v['desc'], 'data': v['data'],
                'type': v.get('signal', 'BUY'), 'source_type': v.get('type', 'KLINE'),
                'is_fav': is_fav
            })

        users = []
        for u in UserPattern.objects.all():
            try:
                data = json.loads(u.data_points) if u.source_type == 'KLINE' else [float(x) for x in
                                                                                   u.data_points.split(',')]
                is_fav = f"USER:{u.id}" in fav_ids
                users.append({
                    'id': u.id, 'name': u.name, 'data': data,
                    'type': 'BUY', 'source_type': u.source_type, 'is_fav': is_fav
                })
            except:
                pass

        return JsonResponse({'code': 200, 'data': {'presets': presets, 'users': users}})
    except Exception as e:
        return JsonResponse({'code': 500, 'msg': str(e)})


@csrf_exempt
def api_pattern_save(request):
    if request.method == 'POST':
        try:
            b = json.loads(request.body)
            d = json.dumps(b['data']) if b['type'] == 'KLINE' else ",".join(map(str, b['data']))
            UserPattern.objects.create(name=b['name'], source_type=b['type'], description=b.get('desc', ''),
                                       data_points=d)
            return JsonResponse({'code': 200})
        except:
            return JsonResponse({'code': 500})
    return JsonResponse({'code': 405})


@csrf_exempt
def api_pattern_delete(request):
    if request.method == 'POST':
        UserPattern.objects.filter(id=json.loads(request.body)['id']).delete()
        return JsonResponse({'code': 200})
    return JsonResponse({'code': 405})


@csrf_exempt
def api_pattern_fav_toggle(request):
    if request.method == 'POST':
        try:
            b = json.loads(request.body)
            o, c = PatternFavorite.objects.get_or_create(pattern_id=str(b['id']),
                                                         pattern_type=b.get('source_type', 'PRESET'))
            if not c: o.delete()
            return JsonResponse({'code': 200, 'status': c})
        except:
            return JsonResponse({'code': 500})
    return JsonResponse({'code': 405})


@csrf_exempt
def api_analyze_pattern_trend(request): return JsonResponse({'code': 200, 'data': {'trend': 'BUY'}})


@csrf_exempt
def api_pattern_quick_verify(request): return JsonResponse(
    {'code': 200, 'data': {'count': 12, 'win_rate': 68.5, 'avg_return': 4.2}})


# ==================== Analysis & Detail API ====================
@csrf_exempt
def api_run_analysis(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            res = run_analysis_core(body.get('pattern_data'), body.get('filters', {}))
            enhanced = []
            for r in res:
                p = float(r['price'])
                r['buy_point'] = round(p * 0.98, 2)
                r['sell_point'] = round(p * 1.05, 2)
                r['holding_period'] = '5天'
                enhanced.append(r)
            return JsonResponse({'code': 200, 'data': enhanced})
        except:
            return JsonResponse({'code': 500})
    return JsonResponse({'code': 405})


@csrf_exempt
def api_stock_detail(request):
    try:
        code = request.GET.get('code', '000001.SZ')
        qs = StockDaily.objects.filter(ts_code=code).order_by('trade_date')
        if not qs.exists(): return JsonResponse({'code': 404, 'msg': '无数据'})

        data = list(qs.values('trade_date', 'open_price', 'close_price', 'low_price', 'high_price', 'vol'))
        df = pd.DataFrame(data)
        df.rename(columns={'open_price': 'open', 'close_price': 'close', 'high_price': 'high', 'low_price': 'low'},
                  inplace=True)

        df = calculate_indicators(df)
        signals = analyze_kline_signals(df)

        # 🔥 辅助函数：安全转 float list
        def sl(col_name):
            if col_name not in df.columns: return [0.0] * len(df)
            return [float(x) if not pd.isna(x) else 0.0 for x in df[col_name]]

        return JsonResponse({
            'code': 200,
            'data': {
                'dates': df['trade_date'].apply(lambda x: x.strftime('%Y-%m-%d')).tolist(),
                'values': df[['open', 'close', 'low', 'high', 'vol']].values.tolist(),
                'indicators': {
                    'MA5': sl('MA5'), 'MA20': sl('MA20'),
                    'K': sl('K'), 'D': sl('D'), 'J': sl('J'),
                    'MACD': sl('MACD'), 'DIF': sl('DIF'), 'DEA': sl('DEA'),
                    'RSI': sl('RSI')
                },
                'signals': signals,
                'basic': {'pe': 22.5, 'industry': '半导体'},
                'funds': {'north_in': 5.2, 'main_in': -1.2}
            }
        })
    except Exception as e:
        return JsonResponse({'code': 500, 'msg': str(e)})


# ==================== Strategy & Trade API ====================
@csrf_exempt
def api_save_strategy(request):
    if request.method == 'POST':
        try:
            b = json.loads(request.body)
            UserStrategy.objects.create(name=b.get('name', '未命名'), criteria=b.get('filters', {}),
                                        is_monitoring=b.get('monitor', False))
            return JsonResponse({'code': 200, 'msg': '保存成功'})
        except:
            return JsonResponse({'code': 500})
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
def api_place_order(request):
    if request.method == 'POST':
        b = json.loads(request.body)
        TradeRecord.objects.create(ts_code=b['code'], trade_date=datetime.date.today(), trade_type=b['type'],
                                   price=b['price'], volume=b['volume'], trigger_condition=b.get('triggerValue', ''))
        return JsonResponse({'code': 200})
    return JsonResponse({'code': 405})


def api_trade_data(request): return JsonResponse({'code': 200, 'data': list(TradeRecord.objects.all().values())})


@csrf_exempt
def api_fav_add(request):
    if request.method == 'POST': FavoriteStock.objects.get_or_create(
        ts_code=json.loads(request.body)['code']); return JsonResponse({'code': 200})


def api_fav_list(request): return JsonResponse({'code': 200, 'data': list(FavoriteStock.objects.all().values())})


@csrf_exempt
def api_run_prediction(request): return JsonResponse(
    {'code': 200, 'data': run_lstm_prediction(json.loads(request.body).get('code'))})


@csrf_exempt
def api_run_backtest(request): return JsonResponse(
    {'code': 200, 'data': run_backtest_strategy(json.loads(request.body).get('code'))})