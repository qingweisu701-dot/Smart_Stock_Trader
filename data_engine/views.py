from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import StockDaily, TradeRecord, UserPattern, FavoriteStock
from algorithms.matcher import run_analysis_core, PRESET_PATTERNS
from algorithms.predictor import run_lstm_prediction
from algorithms.backtest import run_backtest_strategy
import json
import datetime
import pandas as pd


# ==================== 页面路由 ====================
def page_pattern_manage(request): return render(request, 'pattern_manage.html')


def page_analysis(request): return render(request, 'analysis.html')


def page_prediction(request): return render(request, 'prediction_center.html')


def page_trade_history(request): return render(request, 'trade_history.html')


# ==================== 核心 API ====================

@csrf_exempt
def api_run_analysis(request):
    """执行图形分析与筛选"""
    if request.method == 'POST':
        body = json.loads(request.body)
        pattern_data = body.get('pattern_data')  # 数组或None
        filters = body.get('filters', {})

        results = run_analysis_core(pattern_data, filters)
        return JsonResponse({'code': 200, 'data': results})


@csrf_exempt
def api_place_order(request):
    """下单接口 (支持自定义数量、买卖)"""
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            t_type = body.get('type', 'BUY')
            price = float(body['price'])
            vol = int(body.get('volume', 100))

            # 简单记录，不校验资金
            TradeRecord.objects.create(
                ts_code=body['code'],
                trade_date=datetime.date.today(),
                trade_type=t_type,
                price=price,
                volume=vol,
                strategy_name=body.get('strategy', '手动')
            )
            return JsonResponse({'code': 200, 'msg': '委托成功'})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': str(e)})


@csrf_exempt
def api_pattern_list(request):
    """获取所有形态（预设+自定义）"""
    # 1. 预设
    presets = []
    for k, v in PRESET_PATTERNS.items():
        presets.append({'id': k, 'name': v['desc'], 'data': v['data'], 'source': 'SYSTEM', 'type': v['type']})

    # 2. 用户自定义
    customs = UserPattern.objects.all()
    user_list = []
    for p in customs:
        user_list.append({
            'id': f"custom_{p.id}",
            'name': p.name,
            'data': p.get_data_list(),
            'source': 'USER',
            'desc': p.description
        })

    return JsonResponse({'code': 200, 'data': {'presets': presets, 'users': user_list}})


@csrf_exempt
def api_pattern_save(request):
    """保存手绘形态"""
    if request.method == 'POST':
        body = json.loads(request.body)
        UserPattern.objects.create(
            name=body['name'],
            description=body.get('desc', ''),
            data_points=",".join(map(str, body['data']))
        )
        return JsonResponse({'code': 200, 'msg': '保存成功'})


@csrf_exempt
def api_toggle_favorite(request):
    """收藏/取消收藏"""
    if request.method == 'POST':
        body = json.loads(request.body)
        code = body['code']
        action = body.get('action', 'add')

        if action == 'add':
            FavoriteStock.objects.get_or_create(ts_code=code)
        else:
            FavoriteStock.objects.filter(ts_code=code).delete()
        return JsonResponse({'code': 200, 'msg': '操作成功'})


def api_get_favorites(request):
    """获取收藏列表"""
    favs = FavoriteStock.objects.all().values_list('ts_code', flat=True)
    return JsonResponse({'code': 200, 'data': list(favs)})


@csrf_exempt
def api_run_backtest(request):
    """运行回测"""
    if request.method == 'POST':
        body = json.loads(request.body)
        res = run_backtest_strategy(body['code'])
        return JsonResponse({'code': 200, 'data': res})


# 保留原有的 K 线获取和预测接口
def api_get_kline(request):
    code = request.GET.get('code', '000001')
    qs = StockDaily.objects.filter(ts_code=code).order_by('trade_date')
    if not qs.exists(): return JsonResponse({'code': 404, 'msg': '无数据'})

    data = list(qs.values('trade_date', 'open_price', 'close_price', 'low_price', 'high_price', 'vol'))
    df = pd.DataFrame(data)
    if not df.empty:
        df.rename(columns={'open_price': 'open', 'close_price': 'close', 'high_price': 'high', 'low_price': 'low'},
                  inplace=True)
        # 简单均线计算
        df['MA5'] = df['close'].rolling(5).mean().fillna(0)
        df['MA20'] = df['close'].rolling(20).mean().fillna(0)

    return JsonResponse({
        'code': 200,
        'data': {
            'dates': df['trade_date'].apply(lambda x: x.strftime('%Y-%m-%d')).tolist(),
            'values': df[['open', 'close', 'low', 'high', 'vol']].values.tolist(),
            'mas': {'MA5': df['MA5'].tolist(), 'MA20': df['MA20'].tolist()}
        }
    })


@csrf_exempt
def api_run_prediction(request):
    # 复用之前的逻辑
    if request.method == 'POST':
        body = json.loads(request.body)
        res = run_lstm_prediction(body['code'])
        return JsonResponse({'code': 200, 'data': res})
    return JsonResponse({'code': 400})


def api_trade_data(request):
    # 获取交易列表
    records = TradeRecord.objects.all().order_by('-create_time')
    data = [{
        'code': r.ts_code,
        'type': r.trade_type,
        'price': r.price,
        'volume': r.volume,
        'strategy': r.strategy_name,
        'date': r.trade_date.strftime('%Y-%m-%d')
    } for r in records]
    return JsonResponse({'code': 200, 'data': data})