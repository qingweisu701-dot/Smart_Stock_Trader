from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import StockDaily, StockBasic, UserPattern, FavoriteStock, TradeRecord, SystemMessage
from algorithms.matcher import run_analysis_core, PRESET_PATTERNS, analyze_kline_signals, calculate_indicators
from algorithms.predictor import run_lstm_prediction
from algorithms.backtest import run_backtest_strategy
import json, datetime
import pandas as pd
import numpy as np


# ==================== 页面 ====================
def page_pattern_draw(request):
    """图形绘制 - 趋势手绘页"""
    return render(request, 'pattern_draw.html')

def page_pattern_build(request):
    """图形绘制 - K线精调页"""
    return render(request, 'pattern_build.html')

def page_analysis_scan(request):
    """市场分析 - 智能筛选页"""
    return render(request, 'analysis_scan.html')

def page_analysis_fav(request):
    """市场分析 - 观察仓页"""
    return render(request, 'analysis_fav.html')

def page_prediction_ai(request):
    """量化决策 - AI趋势预测页"""
    return render(request, 'prediction_ai.html')

def page_prediction_backtest(request):
    """量化决策 - 历史回测页"""
    return render(request, 'prediction_backtest.html')

def page_trade_history(request):
    """交易中心 - 流水页"""
    return render(request, 'trade_history.html')
# ==================== 1. 图形管理 ====================

@csrf_exempt
def api_analyze_pattern_trend(request):
    """
    [新增] 智能分析用户绘制的图形趋势，给出买卖建议
    """
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            p_type = body.get('type')
            data = body.get('data')  # 可能是 Y轴数组 或 K线对象数组

            trend = "UNKNOWN"
            confidence = 0

            if p_type == 'DRAW':
                # 简单线性回归判断斜率
                y = np.array(data)
                x = np.arange(len(y))
                slope, _ = np.polyfit(x, y, 1)

                if slope > 0.1:
                    trend = 'BUY'
                    confidence = min(90, int(slope * 100))
                elif slope < -0.1:
                    trend = 'SELL'
                    confidence = min(90, int(abs(slope) * 100))
                else:
                    trend = 'SHOCK'  # 震荡

            elif p_type == 'KLINE':
                # K线逻辑：比较最后一根和第一根
                first = data[0]['close']
                last = data[-1]['close']
                change = (last - first) / first

                if change > 0.02:
                    trend = 'BUY'
                elif change < -0.02:
                    trend = 'SELL'
                else:
                    trend = 'SHOCK'

            return JsonResponse({'code': 200, 'data': {'trend': trend, 'msg': 'AI分析完成'}})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': str(e)})


@csrf_exempt
def api_pattern_list(request):
    presets = [{'id': k, 'name': v['desc'], 'data': v['data'], 'type': v['type']} for k, v in PRESET_PATTERNS.items()]
    users = []
    for u in UserPattern.objects.all():
        try:
            data = json.loads(u.data_points) if u.source_type == 'KLINE' else [float(x) for x in
                                                                               u.data_points.split(',')]
            users.append({'id': u.id, 'name': u.name, 'data': data, 'type': 'CUSTOM', 'desc': u.description})
        except:
            pass
    return JsonResponse({'code': 200, 'data': {'presets': presets, 'users': users}})


@csrf_exempt
def api_pattern_save(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            p_type = body.get('type', 'DRAW')
            data = body.get('data')
            data_str = json.dumps(data) if p_type == 'KLINE' else ",".join(map(str, data))

            UserPattern.objects.create(
                name=body['name'], source_type=p_type,
                description=body.get('desc', ''), data_points=data_str
            )
            return JsonResponse({'code': 200, 'msg': '保存成功'})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': str(e)})


# ==================== 2. 市场分析 ====================

@csrf_exempt
def api_run_analysis(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            results = run_analysis_core(body.get('pattern_data'), body.get('filters', {}))
            return JsonResponse({'code': 200, 'data': results})
        except Exception as e:
            print(e)
            return JsonResponse({'code': 500, 'msg': str(e)})
    return JsonResponse({'code': 405})


@csrf_exempt
def api_stock_detail(request):
    code = request.GET.get('code', '000001')
    qs = StockDaily.objects.filter(ts_code=code).order_by('trade_date')
    if not qs.exists(): return JsonResponse({'code': 404, 'msg': '无数据'})

    data = list(qs.values('trade_date', 'open_price', 'close_price', 'low_price', 'high_price', 'vol'))
    df = pd.DataFrame(data)
    df.rename(columns={'open_price': 'open', 'close_price': 'close', 'high_price': 'high', 'low_price': 'low'},
              inplace=True)
    df = calculate_indicators(df)
    signals = analyze_kline_signals(df)

    return JsonResponse({
        'code': 200,
        'data': {
            'dates': df['trade_date'].apply(lambda x: x.strftime('%Y-%m-%d')).tolist(),
            'values': df[['open', 'close', 'low', 'high', 'vol']].values.tolist(),
            'mas': {'MA5': df['MA5'].fillna(0).tolist(), 'MA20': df['MA20'].fillna(0).tolist()},
            'signals': signals
        }
    })


# ==================== 3. 收藏与交易 ====================

def api_fav_list(request):
    """
    [升级] 获取收藏列表，关联股票名称，供前端点击使用
    """
    favs = FavoriteStock.objects.all()
    data = []
    for f in favs:
        # 尝试获取股票名称
        name = f.ts_code
        try:
            basic = StockBasic.objects.get(ts_code=f.ts_code)
            name = basic.name
        except:
            pass

        data.append({
            'code': f.ts_code,
            'name': name,
            'group': f.group,
            'notes': f.notes
        })
    return JsonResponse({'code': 200, 'data': data})


@csrf_exempt
def api_fav_add(request):
    if request.method == 'POST':
        body = json.loads(request.body)
        FavoriteStock.objects.get_or_create(ts_code=body['code'], defaults={'group': body.get('group', 'DEFAULT')})
        return JsonResponse({'code': 200})


@csrf_exempt
def api_place_order(request):
    if request.method == 'POST':
        body = json.loads(request.body)
        TradeRecord.objects.create(
            ts_code=body['code'], trade_date=datetime.date.today(),
            trade_type=body.get('type', 'BUY'), price=float(body['price']), volume=int(body.get('volume', 100))
        )
        return JsonResponse({'code': 200})


def api_trade_data(request):
    records = TradeRecord.objects.all().order_by('-create_time')
    data = [{'date': r.trade_date.strftime('%Y-%m-%d'), 'code': r.ts_code, 'type': r.trade_type,
             'price': r.price, 'volume': r.volume, 'strategy': r.strategy_name} for r in records]
    return JsonResponse({'code': 200, 'data': data})


# ==================== 4. 预测与消息 ====================

@csrf_exempt
def api_run_prediction(request):
    """[修复] 预测接口"""
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            res = run_lstm_prediction(body['code'])
            return JsonResponse({'code': 200, 'data': res})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': str(e)})
    return JsonResponse({'code': 405})


@csrf_exempt
def api_run_backtest(request):
    if request.method == 'POST':
        body = json.loads(request.body)
        res = run_backtest_strategy(body['code'])
        return JsonResponse({'code': 200, 'data': res})


def api_check_messages(request):
    msgs = list(SystemMessage.objects.filter(is_read=False).values()[:5])
    return JsonResponse({'code': 200, 'data': msgs})