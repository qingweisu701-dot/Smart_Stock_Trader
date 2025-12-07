from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import F
from .models import StockDaily, TradeRecord
from algorithms.matcher import run_pattern_matching
import json
import datetime
from algorithms.predictor import run_lstm_prediction

def kline_page(request):
    """返回前端页面"""
    return render(request, 'kline_chart.html')


def get_kline_data(request):
    """API: 获取K线数据"""
    code = request.GET.get('code', '000001')
    queryset = StockDaily.objects.filter(ts_code=code).order_by('trade_date')

    if not queryset.exists():
        return JsonResponse({'code': 404, 'msg': '未找到该股票数据', 'data': []})

    dates = []
    values = []
    for row in queryset:
        dates.append(row.trade_date.strftime('%Y-%m-%d'))
        values.append([row.open, row.close, row.low, row.high, row.vol])

    return JsonResponse({
        'code': 200,
        'msg': 'success',
        'data': {'ts_code': code, 'dates': dates, 'values': values}
    })


@csrf_exempt
def match_pattern(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            user_prices = body.get('prices', [])
            mode = body.get('mode', 'BUY')
            filters = body.get('filters', {})  # <--- 获取筛选条件

            # 传给算法
            top_stocks = run_pattern_matching(user_prices, mode=mode, filters=filters)

            return JsonResponse({'code': 200, 'msg': '匹配完成', 'data': top_stocks})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': str(e)})
    return JsonResponse({'code': 405, 'msg': 'Method Not Allowed'})

@csrf_exempt
def place_order(request):
    """
    API: 模拟下单接口 (记录交易)
    """
    if request.method == 'POST':
        try:
            body = json.loads(request.body)

            # 创建交易记录
            TradeRecord.objects.create(
                ts_code=body['code'],
                trade_date=body.get('date', datetime.date.today()),
                trade_type=body['type'],  # 'BUY' 或 'SELL'
                price=body['price'],
                volume=body.get('volume', 100),  # 默认100手
                strategy_name=body.get('trigger', '手动图形匹配')
            )

            return JsonResponse({'code': 200, 'msg': '交易记录已保存'})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': str(e)})

    return JsonResponse({'code': 405, 'msg': '仅支持 POST 请求'})


def prediction_page(request):
    """返回预测中心的前端页面"""
    return render(request, 'prediction_center.html')


@csrf_exempt
def get_prediction(request):
    """API: 获取某只股票的预测结果"""
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            code = body.get('code', '000001')

            result = run_lstm_prediction(code)

            if result:
                return JsonResponse({'code': 200, 'msg': 'success', 'data': result})
            else:
                return JsonResponse({'code': 404, 'msg': '数据不足，无法预测'})

        except Exception as e:
            return JsonResponse({'code': 500, 'msg': str(e)})

    return JsonResponse({'code': 405, 'msg': 'Method Not Allowed'})