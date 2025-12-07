from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import StockDaily, TradeRecord
from algorithms.matcher import run_pattern_matching
from algorithms.predictor import run_lstm_prediction
import json
import datetime
import pandas as pd


# ==========================================
# 1. 页面视图 (返回 HTML)
# ==========================================

def kline_page(request):
    """K线筛选主页面"""
    return render(request, 'kline_chart.html')


def history_page(request):
    """历史回测页面"""
    return render(request, 'trade_history.html')


def prediction_page(request):
    """量化预测页面"""
    return render(request, 'prediction_center.html')


# ==========================================
# 2. 数据 API (返回 JSON)
# ==========================================

def get_kline_data(request):
    """【已修复】获取K线数据 (含均线和成交量)"""
    code = request.GET.get('code', '000001')
    queryset = StockDaily.objects.filter(ts_code=code).order_by('trade_date')

    if not queryset.exists():
        return JsonResponse({'code': 404, 'msg': '未找到该股票数据', 'data': []})

    # -------------------------------------------------------
    # 修复核心：读取数据库的新字段名 (_price)
    # -------------------------------------------------------
    data_list = list(queryset.values(
        'trade_date',
        'open_price',
        'close_price',
        'low_price',
        'high_price',
        'vol'
    ))

    df = pd.DataFrame(data_list)

    # -------------------------------------------------------
    # 修复核心：将列名重命名回 open/close/high/low
    # 这样下面的计算逻辑和前端返回值都不用改
    # -------------------------------------------------------
    if not df.empty:
        df.rename(columns={
            'open_price': 'open',
            'close_price': 'close',
            'high_price': 'high',
            'low_price': 'low'
        }, inplace=True)

    # 计算均线 (现在 df['close'] 可以正常访问了)
    df['MA5'] = df['close'].rolling(window=5).mean()
    df['MA10'] = df['close'].rolling(window=10).mean()
    df['MA20'] = df['close'].rolling(window=20).mean()
    df = df.fillna(0)

    # 准备返回给前端的数据结构
    dates = df['trade_date'].apply(lambda x: x.strftime('%Y-%m-%d')).tolist()
    # 这里的顺序必须对应前端 ECharts 的 dataset
    values = df[['open', 'close', 'low', 'high', 'vol']].values.tolist()

    ma_data = {
        'MA5': df['MA5'].tolist(),
        'MA10': df['MA10'].tolist(),
        'MA20': df['MA20'].tolist()
    }

    volumes = []
    for i, row in df.iterrows():
        # 判断涨跌颜色
        sign = 1 if row['close'] >= row['open'] else -1
        volumes.append([i, row['vol'], sign])

    return JsonResponse({
        'code': 200,
        'msg': 'success',
        'data': {
            'ts_code': code,
            'dates': dates,
            'values': values,
            'mas': ma_data,
            'volumes': volumes
        }
    })


@csrf_exempt
def match_pattern(request):
    """核心匹配接口"""
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            user_prices = body.get('prices', [])
            mode = body.get('mode', 'BUY')
            filters = body.get('filters', {})

            # 注意：如果 run_pattern_matching 内部也查询了数据库
            # 你可能也需要去修改 algorithms/matcher.py 里的字段名
            top_stocks = run_pattern_matching(user_prices, mode=mode, filters=filters)

            return JsonResponse({'code': 200, 'msg': '匹配完成', 'data': top_stocks})
        except Exception as e:
            # 打印详细错误到后台终端，方便调试
            print(f"Error in match_pattern: {e}")
            return JsonResponse({'code': 500, 'msg': str(e)})
    return JsonResponse({'code': 405, 'msg': 'Method Not Allowed'})


@csrf_exempt
def place_order(request):
    """模拟下单接口"""
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            TradeRecord.objects.create(
                ts_code=body['code'],
                # 防止日期为空
                trade_date=body.get('date', datetime.date.today()),
                trade_type=body['type'],
                price=body['price'],
                volume=body.get('volume', 100),
                strategy_name=body.get('trigger', '手动交易')
            )
            return JsonResponse({'code': 200, 'msg': '交易记录已保存'})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': str(e)})
    return JsonResponse({'code': 405, 'msg': 'Method Not Allowed'})


def get_trade_history(request):
    """获取交易历史数据"""
    records = TradeRecord.objects.all().order_by('-create_time')
    data = []
    for r in records:
        data.append({
            'code': r.ts_code,
            'date': r.trade_date.strftime('%Y-%m-%d'),
            'type': r.trade_type,
            'price': r.price,
            'volume': r.volume,
            'strategy': r.strategy_name,
            'time': r.create_time.strftime('%Y-%m-%d %H:%M:%S')
        })
    return JsonResponse({'code': 200, 'msg': 'success', 'data': data})


@csrf_exempt
def get_prediction(request):
    """预测接口"""
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            code = body.get('code', '000001')

            # 注意：如果 run_lstm_prediction 内部查询了数据库
            # 你可能也需要去修改 algorithms/predictor.py
            result = run_lstm_prediction(code)

            if result:
                return JsonResponse({'code': 200, 'msg': 'success', 'data': result})
            else:
                return JsonResponse({'code': 404, 'msg': '数据不足'})
        except Exception as e:
            print(f"Error in prediction: {e}")
            return JsonResponse({'code': 500, 'msg': str(e)})
    return JsonResponse({'code': 405, 'msg': 'Method Not Allowed'})