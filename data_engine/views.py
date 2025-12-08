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


# ==================== 页面渲染 (三台一流水) ====================
def page_pattern_lab(request): return render(request, 'pattern_lab.html')  # 图形实验室


def page_market_scan(request): return render(request, 'market_scan.html')  # 市场扫描


def page_decision_center(request): return render(request, 'decision_center.html')  # 决策中心(含收藏/回测)
def page_pattern_draw(request):
    return render(request, 'pattern_manage.html') # 注意：复用以前的 manage html 作为绘制页

def page_pattern_list(request):
    """【新】图形清单独立页面"""
    return render(request, 'pattern_list.html')

def page_analysis_scan(request):
    return render(request, 'analysis_scan.html')

def page_trade_history(request): return render(request, 'trade_history.html')  # 交易流水


# ==================== API: 图形管理 ====================
@csrf_exempt
def api_pattern_delete(request):
    """【找回】删除形态功能"""
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            UserPattern.objects.filter(id=body['id']).delete()
            return JsonResponse({'code': 200, 'msg': '删除成功'})
        except:
            return JsonResponse({'code': 500})
    return JsonResponse({'code': 405})


# ... (保持 api_pattern_list, api_pattern_save, api_analyze_pattern_trend 不变) ...
# 请确保 api_pattern_list 能返回 id, name, type, data

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
        body = json.loads(request.body)
        p_type = body.get('type', 'DRAW')
        data = body.get('data')
        data_str = json.dumps(data) if p_type == 'KLINE' else ",".join(map(str, data))
        UserPattern.objects.create(name=body['name'], source_type=p_type, description=body.get('desc', ''),
                                   data_points=data_str)
        return JsonResponse({'code': 200})


@csrf_exempt
def api_analyze_pattern_trend(request):
    # 简单模拟趋势分析
    return JsonResponse({'code': 200, 'data': {'trend': 'BUY'}})


# ==================== API: 市场分析 ====================
@csrf_exempt
def api_run_analysis(request):
    if request.method == 'POST':
        body = json.loads(request.body)
        results = run_analysis_core(body.get('pattern_data'), body.get('filters', {}))
        return JsonResponse({'code': 200, 'data': results})
    return JsonResponse({'code': 405})


# ==================== API: 决策支持 (详情/预测) ====================
@csrf_exempt
def api_stock_detail(request):
    """【重点】详情页数据，包含 K 线和买卖信号"""
    code = request.GET.get('code')
    qs = StockDaily.objects.filter(ts_code=code).order_by('trade_date')
    if not qs.exists(): return JsonResponse({'code': 404})

    data = list(qs.values('trade_date', 'open_price', 'close_price', 'low_price', 'high_price', 'vol'))
    df = pd.DataFrame(data)
    df.rename(columns={'open_price': 'open', 'close_price': 'close', 'high_price': 'high', 'low_price': 'low'},
              inplace=True)
    df = calculate_indicators(df)
    signals = analyze_kline_signals(df)  # 计算买卖点

    return JsonResponse({
        'code': 200,
        'data': {
            'dates': df['trade_date'].apply(lambda x: x.strftime('%Y-%m-%d')).tolist(),
            'values': df[['open', 'close', 'low', 'high', 'vol']].values.tolist(),
            'mas': {'MA5': df['MA5'].tolist(), 'MA20': df['MA20'].tolist()},
            'signals': signals
        }
    })


# ... (保持 api_fav_list, api_fav_add, api_run_prediction, api_run_backtest 等不变) ...
# 确保 api_fav_list 返回 name, code, group
def api_fav_list(request):
    favs = FavoriteStock.objects.all()
    data = []
    for f in favs:
        name = f.ts_code
        try:
            name = StockBasic.objects.get(ts_code=f.ts_code).name
        except:
            pass
        data.append({'code': f.ts_code, 'name': name, 'group': f.group})
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
        TradeRecord.objects.create(ts_code=body['code'], trade_date=datetime.date.today(), trade_type=body['type'],
                                   price=body['price'], volume=body['volume'])
        return JsonResponse({'code': 200})


def api_trade_data(request):
    records = TradeRecord.objects.all().order_by('-create_time')
    return JsonResponse({'code': 200, 'data': list(records.values())})


@csrf_exempt
def api_run_prediction(request):
    if request.method == 'POST':
        res = run_lstm_prediction(json.loads(request.body).get('code'))
        return JsonResponse({'code': 200, 'data': res})


@csrf_exempt
def api_run_backtest(request):
    if request.method == 'POST':
        res = run_backtest_strategy(json.loads(request.body).get('code'))
        return JsonResponse({'code': 200, 'data': res})


def api_check_messages(request): return JsonResponse({'code': 200, 'data': []})