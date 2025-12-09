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


# ==================== 1. 页面渲染视图 ====================

def page_dashboard(request):
    return render(request, 'dashboard.html')


def page_pattern_lab(request):
    return render(request, 'pattern_lab.html')


def page_analysis_scan(request):
    return render(request, 'analysis_scan.html')


def page_analysis_fav(request):
    return render(request, 'analysis_fav.html')


def page_decision_center(request):
    return render(request, 'decision_center.html')


def page_trade_history(request):
    return render(request, 'trade_history.html')


def page_profit_analysis(request):
    return render(request, 'profit_analysis.html')


def page_pattern_draw(request):
    return render(request, 'pattern_lab.html')


# ==================== 2. 首页仪表盘与监控 API ====================

@csrf_exempt
def api_dashboard_data(request):
    """
    首页数据接口：包含全套模拟指标，用于展示三窗联动效果
    """
    try:
        index_type = request.GET.get('type', '000001.SH')
        # 基础点位
        base_map = {
            '000001.SH': 3280,
            '399001.SZ': 10500,
            '399006.SZ': 2150,
            '000300.SH': 3900,
            '000688.SH': 980
        }
        base = base_map.get(index_type, 3000)

        # 1. 生成模拟K线
        dates = pd.date_range(end=datetime.date.today(), periods=100).strftime('%Y-%m-%d').tolist()
        data_list = []
        curr = base

        for d in dates:
            o = curr
            c = o * (1 + np.random.uniform(-0.02, 0.02))
            h = max(o, c) * 1.01
            l = min(o, c) * 0.99
            v = np.random.randint(1000, 5000)
            data_list.append({
                'trade_date': d,
                'open': o,
                'close': c,
                'high': h,
                'low': l,
                'vol': v
            })
            curr = c

        # 2. 转为 DataFrame 并计算指标
        df = pd.DataFrame(data_list)
        df = calculate_indicators(df)

        # 3. 辅助函数：安全转列表 (防空值 + 强转Python类型)
        def sl(col_name):
            if col_name not in df.columns:
                return [0.0] * len(df)
            return [float(x) if not pd.isna(x) else 0.0 for x in df[col_name]]

        # 4. 构造 K 线数组 [date, open, close, low, high, vol]
        # 注意：前端 ECharts 通常需要 open, close, low, high
        kline_values = df[['open', 'close', 'low', 'high', 'vol']].values.tolist()

        # 5. 构造指标字典
        indicators = {
            'MA5': sl('MA5'),
            'MA10': sl('MA10'),
            'MA20': sl('MA20'),
            'K': sl('K'), 'D': sl('D'), 'J': sl('J'),
            'MACD': sl('MACD'), 'DIF': sl('DIF'), 'DEA': sl('DEA'),
            'RSI': sl('RSI')
        }

        # 6. 市场概况与快照
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

        last = df.iloc[-1]
        prev = df.iloc[-2]
        change_val = last['close'] - prev['close']
        change_pct = change_val / prev['close'] * 100

        snapshot = {
            'name': '当前指数',
            'price': round(last['close'], 2),
            'change': f"{change_pct:.2f}%",
            'is_up': bool(change_val > 0),
            'volume': f"{int(last['vol'] / 10)}亿"
        }

        return JsonResponse({
            'code': 200,
            'data': {
                'market': market,
                'index_data': {
                    'dates': dates,
                    'values': kline_values,
                    'indicators': indicators
                },
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
    """
    策略巡检与消息推送
    """
    try:
        # 模拟后台巡检
        strats = UserStrategy.objects.filter(is_monitoring=True)
        for s in strats:
            # 简单去重
            if not SystemMessage.objects.filter(title__contains=s.name, is_read=False).exists():
                if np.random.rand() > 0.7:
                    SystemMessage.objects.create(
                        title=f"策略命中: {s.name}",
                        content=f"您的策略【{s.name}】监控到新的交易机会，请及时查看。",
                        related_code="000001.SZ"
                    )

        msgs = list(SystemMessage.objects.filter(is_read=False).order_by('-create_time').values()[:3])
        return JsonResponse({'code': 200, 'data': msgs})
    except Exception:
        return JsonResponse({'code': 200, 'data': []})


# ==================== 3. 形态管理 API ====================

@csrf_exempt
def api_pattern_list(request):
    try:
        fav_qs = PatternFavorite.objects.all()
        fav_ids = set([f"{f.pattern_type}:{f.pattern_id}" for f in fav_qs])

        presets = []
        for k, v in PRESET_PATTERNS.items():
            is_fav = f"PRESET:{k}" in fav_ids
            presets.append({
                'id': k,
                'name': v['desc'],
                'data': v['data'],
                'type': v.get('signal', 'BUY'),
                'source_type': v.get('type', 'KLINE'),
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
                    'id': u.id,
                    'name': u.name,
                    'data': data,
                    'type': signal,
                    'source_type': u.source_type,
                    'is_fav': is_fav
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
            UserPattern.objects.create(
                name=b['name'],
                source_type=b['type'],
                description=b.get('desc', ''),
                data_points=d
            )
            return JsonResponse({'code': 200})
        except Exception:
            return JsonResponse({'code': 500})
    return JsonResponse({'code': 405})


@csrf_exempt
def api_pattern_delete(request):
    if request.method == 'POST':
        try:
            UserPattern.objects.filter(id=json.loads(request.body)['id']).delete()
            return JsonResponse({'code': 200})
        except Exception:
            return JsonResponse({'code': 500})
    return JsonResponse({'code': 405})


@csrf_exempt
def api_pattern_fav_toggle(request):
    if request.method == 'POST':
        try:
            b = json.loads(request.body)
            pid = str(b['id'])
            ptype = b.get('source_type', 'PRESET')
            if ptype == 'CUSTOM':
                ptype = 'USER'

            o, c = PatternFavorite.objects.get_or_create(pattern_id=pid, pattern_type=ptype)
            if not c:
                o.delete()
            return JsonResponse({'code': 200, 'status': c})
        except Exception:
            return JsonResponse({'code': 500})
    return JsonResponse({'code': 405})


@csrf_exempt
def api_analyze_pattern_trend(request):
    return JsonResponse({'code': 200, 'data': {'trend': 'BUY'}})


@csrf_exempt
def api_pattern_quick_verify(request):
    return JsonResponse({'code': 200, 'data': {'count': 12, 'win_rate': 68.5, 'avg_return': 4.2}})


# ==================== 4. 市场扫描与详情 API ====================

@csrf_exempt
def api_run_analysis(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            # 调用核心算法
            base_results = run_analysis_core(body.get('pattern_data'), body.get('filters', {}))

            # 增强数据：买卖点、周期
            enhanced_results = []
            for r in base_results:
                price = float(r['price'])
                r['buy_point'] = round(price * 0.98, 2)
                r['sell_point'] = round(price * 1.05, 2)
                r['holding_period'] = '5天'
                enhanced_results.append(r)

            return JsonResponse({'code': 200, 'data': enhanced_results})
        except Exception:
            return JsonResponse({'code': 500})
    return JsonResponse({'code': 405})


@csrf_exempt
def api_stock_detail(request):
    """
    🔥 核心修复：确保指标数据安全返回
    """
    try:
        code = request.GET.get('code', '000001.SZ')
        qs = StockDaily.objects.filter(ts_code=code).order_by('trade_date')

        # 空数据防御
        if not qs.exists():
            return JsonResponse({'code': 404, 'msg': '无数据'})

        data = list(qs.values('trade_date', 'open_price', 'close_price', 'low_price', 'high_price', 'vol'))
        df = pd.DataFrame(data)
        df.rename(columns={'open_price': 'open', 'close_price': 'close', 'high_price': 'high', 'low_price': 'low'},
                  inplace=True)

        # 计算指标
        df = calculate_indicators(df)
        signals = analyze_kline_signals(df)

        # 安全转换函数
        def sl(col_name):
            if col_name not in df.columns:
                return [0.0] * len(df)
            return [float(x) if not pd.isna(x) else 0.0 for x in df[col_name]]

        return JsonResponse({
            'code': 200,
            'data': {
                'dates': df['trade_date'].apply(lambda x: x.strftime('%Y-%m-%d')).tolist(),
                'values': df[['open', 'close', 'low', 'high', 'vol']].values.tolist(),
                'indicators': {
                    'MA5': sl('MA5'),
                    'MA10': sl('MA10'),
                    'MA20': sl('MA20'),
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


# ==================== 5. 策略与交易 API ====================

@csrf_exempt
def api_save_strategy(request):
    if request.method == 'POST':
        try:
            b = json.loads(request.body)
            UserStrategy.objects.create(
                name=b.get('name', '未命名'),
                criteria=b.get('filters', {}),
                is_monitoring=b.get('monitor', False)
            )
            return JsonResponse({'code': 200, 'msg': '保存成功'})
        except Exception:
            return JsonResponse({'code': 500})
    return JsonResponse({'code': 405})


def api_list_strategies(request):
    return JsonResponse({'code': 200, 'data': list(UserStrategy.objects.all().values())})


@csrf_exempt
def api_toggle_strategy_monitor(request):
    if request.method == 'POST':
        try:
            s = UserStrategy.objects.get(id=json.loads(request.body)['id'])
            s.is_monitoring = not s.is_monitoring
            s.save()
            return JsonResponse({'code': 200, 'status': s.is_monitoring})
        except Exception:
            return JsonResponse({'code': 500})
    return JsonResponse({'code': 405})


@csrf_exempt
def api_delete_strategy(request):
    if request.method == 'POST':
        try:
            UserStrategy.objects.filter(id=json.loads(request.body)['id']).delete()
            return JsonResponse({'code': 200})
        except Exception:
            return JsonResponse({'code': 500})
    return JsonResponse({'code': 405})


@csrf_exempt
def api_place_order(request):
    if request.method == 'POST':
        try:
            b = json.loads(request.body)
            TradeRecord.objects.create(
                ts_code=b['code'],
                trade_date=datetime.date.today(),
                trade_type=b['type'],
                price=float(b['price']),
                volume=int(b['volume']),
                trigger_condition=b.get('triggerValue', ''),
                order_validity=b.get('valid', 'day')
            )
            return JsonResponse({'code': 200})
        except Exception:
            return JsonResponse({'code': 500})
    return JsonResponse({'code': 405})


def api_trade_data(request):
    return JsonResponse({'code': 200, 'data': list(TradeRecord.objects.all().values())})


# ==================== 6. 其他通用 API ====================

@csrf_exempt
def api_fav_add(request):
    if request.method == 'POST':
        try:
            FavoriteStock.objects.get_or_create(ts_code=json.loads(request.body)['code'])
            return JsonResponse({'code': 200})
        except Exception:
            return JsonResponse({'code': 500})
    return JsonResponse({'code': 405})


def api_fav_list(request):
    return JsonResponse({'code': 200, 'data': list(FavoriteStock.objects.all().values())})


@csrf_exempt
def api_run_prediction(request):
    return JsonResponse({'code': 200, 'data': run_lstm_prediction(json.loads(request.body).get('code'))})


@csrf_exempt
def api_run_backtest(request):
    return JsonResponse({'code': 200, 'data': run_backtest_strategy(json.loads(request.body).get('code'))})