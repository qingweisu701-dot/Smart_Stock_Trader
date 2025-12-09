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


# ==================== 页面渲染视图 ====================
def page_dashboard(request): return render(request, 'dashboard.html')


def page_pattern_lab(request): return render(request, 'pattern_lab.html')


def page_analysis_scan(request): return render(request, 'analysis_scan.html')


def page_analysis_fav(request): return render(request, 'analysis_fav.html')


def page_decision_center(request): return render(request, 'decision_center.html')


def page_trade_history(request): return render(request, 'trade_history.html')


def page_profit_analysis(request): return render(request, 'profit_analysis.html')  # 🔥 补全页面


# 兼容旧路由
def page_pattern_draw(request): return render(request, 'pattern_lab.html')


def page_prediction(request): return render(request, 'decision_center.html')


# ==================== 1. 首页仪表盘 API ====================
@csrf_exempt
def api_dashboard_data(request):
    try:
        index_type = request.GET.get('type', '000001.SH')
        # 基础点位映射
        base_map = {
            '000001.SH': 3280, '399001.SZ': 10500, '399006.SZ': 2150,
            '000300.SH': 3900, '000688.SH': 980
        }
        base_price = base_map.get(index_type, 3000)

        # 模拟 K 线
        dates = pd.date_range(end=datetime.date.today(), periods=100).strftime('%Y-%m-%d').tolist()
        kline_data = []
        curr = base_price

        for d in dates:
            o = curr
            c = o * (1 + np.random.uniform(-0.02, 0.02))
            h = max(o, c) * 1.01
            l = min(o, c) * 0.99
            v = np.random.randint(1000, 5000)
            kline_data.append([d, round(o, 2), round(c, 2), round(l, 2), round(h, 2), v])
            curr = c

        # 市场概况
        market = {
            'up_count': np.random.randint(2000, 3000),
            'down_count': np.random.randint(1000, 2000),
            'volume': '8800亿',
            'hot_sector': '人工智能'
        }

        # 信号预警
        signals = [
            {'code': '600519.SH', 'name': '贵州茅台', 'pattern': '五浪上涨', 'change': 2.1},
            {'code': '300750.SZ', 'name': '宁德时代', 'pattern': 'MACD金叉', 'change': 1.5}
        ]

        # 顶部卡片快照
        last = kline_data[-1]
        prev = kline_data[-2]
        change_pct = (last[2] - prev[2]) / prev[2] * 100
        snapshot = {
            'name': '当前指数',
            'price': last[2],
            'change': f"{change_pct:.2f}%",
            'is_up': bool(change_pct > 0),
            'volume': f"{last[5] / 10}亿"
        }

        return JsonResponse({'code': 200, 'data': {
            'market': market, 'index_data': kline_data, 'signals': signals, 'snapshot': snapshot
        }})
    except Exception as e:
        return JsonResponse({'code': 500, 'msg': str(e)})


# ==================== 2. 图形管理 API ====================
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
                signal = 'BUY' if 'BUY' in u.description else 'SELL'
                users.append({
                    'id': u.id, 'name': u.name, 'data': data,
                    'type': signal, 'source_type': u.source_type, 'is_fav': is_fav
                })
            except:
                pass

        return JsonResponse({'code': 200, 'data': {'presets': presets, 'users': users}})
    except Exception as e:
        return JsonResponse({'code': 500, 'msg': str(e)})


@csrf_exempt
def api_pattern_fav_toggle(request):
    """收藏形态 (已修复缩进问题)"""
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            pid = str(body.get('id'))
            ptype = body.get('source_type', 'PRESET')
            if ptype == 'CUSTOM':
                ptype = 'USER'

            obj, created = PatternFavorite.objects.get_or_create(pattern_id=pid, pattern_type=ptype)

            if not created:
                obj.delete()

            return JsonResponse({'code': 200, 'status': created})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': str(e)})
    return JsonResponse({'code': 405})


@csrf_exempt
def api_pattern_save(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            p_type = body.get('type', 'DRAW')
            data_pts = json.dumps(body['data']) if p_type == 'KLINE' else ",".join(map(str, body['data']))

            UserPattern.objects.create(
                name=body['name'], source_type=p_type,
                description=body.get('desc', ''), data_points=data_pts
            )
            return JsonResponse({'code': 200})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': str(e)})
    return JsonResponse({'code': 405})


@csrf_exempt
def api_pattern_delete(request):
    if request.method == 'POST':
        UserPattern.objects.filter(id=json.loads(request.body)['id']).delete()
        return JsonResponse({'code': 200})
    return JsonResponse({'code': 405})


@csrf_exempt
def api_analyze_pattern_trend(request):
    return JsonResponse({'code': 200, 'data': {'trend': 'BUY'}})


@csrf_exempt
def api_pattern_quick_verify(request):
    # 简单的历史回测模拟
    return JsonResponse({'code': 200, 'data': {'count': 12, 'win_rate': 68.5, 'avg_return': 4.2}})


# ==================== 3. 市场扫描与分析 API ====================
@csrf_exempt
def api_run_analysis(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            # 调用核心算法
            base_results = run_analysis_core(body.get('pattern_data'), body.get('filters', {}))

            # 🔥 增强：添加买卖点建议
            enhanced = []
            for r in base_results:
                price = float(r['price'])
                r['buy_point'] = round(price * 0.98, 2)
                r['sell_point'] = round(price * 1.05, 2)
                r['holding_period'] = f"{np.random.randint(3, 10)}天"
                enhanced.append(r)

            return JsonResponse({'code': 200, 'data': enhanced})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': str(e)})
    return JsonResponse({'code': 405})


@csrf_exempt
def api_save_strategy(request):
    """保存用户策略"""
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


# ==================== 4. 交易与详情 API ====================
@csrf_exempt
def api_stock_detail(request):
    code = request.GET.get('code', '000001.SZ')
    qs = StockDaily.objects.filter(ts_code=code).order_by('trade_date')
    if not qs.exists(): return JsonResponse({'code': 404})

    data = list(qs.values('trade_date', 'open_price', 'close_price', 'high_price', 'low_price', 'vol'))
    df = pd.DataFrame(data)
    df.rename(columns={'open_price': 'open', 'close_price': 'close', 'high_price': 'high', 'low_price': 'low'},
              inplace=True)

    df = calculate_indicators(df)
    signals = analyze_kline_signals(df)

    def sl(s): return [float(x) if not pd.isna(x) else 0 for x in s]

    return JsonResponse({'code': 200, 'data': {
        'dates': df['trade_date'].apply(lambda x: x.strftime('%Y-%m-%d')).tolist(),
        'values': df[['open', 'close', 'low', 'high', 'vol']].values.tolist(),
        'indicators': {
            'MA5': sl(df['MA5']), 'K': sl(df['K']), 'D': sl(df['D']), 'J': sl(df['J'])
        },
        'signals': signals,
        'basic': {'pe': 22.5, 'industry': '半导体'},
        'funds': {'north_in': 5.2, 'main_in': -1.2}
    }})


@csrf_exempt
def api_place_order(request):
    """提交模拟交易/条件单"""
    if request.method == 'POST':
        try:
            b = json.loads(request.body)
            TradeRecord.objects.create(
                ts_code=b['code'],
                trade_date=datetime.date.today(),
                trade_type=b['type'],
                price=float(b['price']),
                volume=int(b['volume']),
                # 保存条件单信息
                trigger_condition=f"{b.get('conditionType')} {b.get('triggerValue')}",
                order_validity=b.get('valid', 'day')
            )
            return JsonResponse({'code': 200})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': str(e)})
    return JsonResponse({'code': 405})


def api_trade_data(request):
    return JsonResponse({'code': 200, 'data': list(TradeRecord.objects.all().values())})


# ... (Fav, Prediction, Backtest 保持不变) ...
@csrf_exempt
def api_fav_add(request):
    if request.method == 'POST': FavoriteStock.objects.get_or_create(
        ts_code=json.loads(request.body)['code']); return JsonResponse({'code': 200})
    return JsonResponse({'code': 405})


def api_fav_list(request):
    return JsonResponse({'code': 200, 'data': list(FavoriteStock.objects.all().values())})


@csrf_exempt
def api_run_prediction(request):
    return JsonResponse({'code': 200, 'data': run_lstm_prediction(json.loads(request.body).get('code'))})


@csrf_exempt
def api_run_backtest(request):
    return JsonResponse({'code': 200, 'data': run_backtest_strategy(json.loads(request.body).get('code'))})


def api_check_messages(request): return JsonResponse({'code': 200, 'data': []})