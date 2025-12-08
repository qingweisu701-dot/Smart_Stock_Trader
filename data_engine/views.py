from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import StockDaily, StockBasic, UserPattern, FavoriteStock, TradeRecord, SystemMessage
# 引入算法模块
from algorithms.matcher import run_analysis_core, PRESET_PATTERNS, analyze_kline_signals, calculate_indicators
from algorithms.predictor import run_lstm_prediction
from algorithms.backtest import run_backtest_strategy

import json, datetime
import pandas as pd


# ==========================================
# 1. 页面渲染视图 (Page Views)
# ==========================================
def page_pattern_manage(request):
    """图形管理实验室页面"""
    return render(request, 'pattern_manage.html')


def page_analysis(request):
    """市场扫描与分析页面"""
    return render(request, 'analysis.html')


def page_prediction(request):
    """收益回测与AI页面"""
    return render(request, 'prediction_center.html')


def page_trade_history(request):
    """模拟交易流水页面"""
    return render(request, 'trade_history.html')


# ==========================================
# 2. 图形管理 API
# ==========================================
@csrf_exempt
def api_pattern_list(request):
    """获取所有形态（预设+自定义）"""
    # 1. 系统预设
    presets = []
    for k, v in PRESET_PATTERNS.items():
        presets.append({
            'id': k,
            'name': v['desc'],
            'data': v['data'],
            'type': v['type']
        })

    # 2. 用户自定义
    users = []
    user_patterns = UserPattern.objects.all()
    for u in user_patterns:
        data = []
        # 尝试解析数据
        try:
            if u.source_type == 'KLINE':
                data = json.loads(u.data_points)
            else:
                data = [float(x) for x in u.data_points.split(',')]
        except:
            data = []  # 数据格式错误容错

        users.append({
            'id': u.id,
            'name': u.name,
            'data': data,
            'type': 'USER'
        })

    return JsonResponse({'code': 200, 'data': {'presets': presets, 'users': users}})


@csrf_exempt
def api_pattern_save(request):
    """保存用户形态"""
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            p_type = body.get('type', 'DRAW')  # DRAW 或 KLINE
            data = body.get('data')

            # 格式化存储数据
            if p_type == 'DRAW':
                # 数组转字符串 "0.1,0.2..."
                data_str = ",".join(map(str, data))
            else:
                # 对象数组转JSON字符串
                data_str = json.dumps(data)

            UserPattern.objects.create(
                name=body['name'],
                source_type=p_type,
                description=body.get('desc', ''),
                data_points=data_str
            )
            return JsonResponse({'code': 200, 'msg': '保存成功'})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': str(e)})
    return JsonResponse({'code': 405})


# ==========================================
# 3. 市场分析 API
# ==========================================
@csrf_exempt
def api_run_analysis(request):
    """执行全市场扫描"""
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            # 获取参数
            p_data = body.get('pattern_data')
            filters = body.get('filters', {})

            # 调用核心算法 (matcher.py)
            results = run_analysis_core(p_data, filters)

            # 模拟推送：如果发现高置信度机会，生成系统消息
            for r in results:
                if r['confidence'] > 85 and r['match_type'] == 'BUY':
                    title = f"🚀 机会提醒: {r['name']}"
                    # 避免重复发送
                    if not SystemMessage.objects.filter(title=title).exists():
                        SystemMessage.objects.create(
                            title=title,
                            content=f"{r['name']}({r['code']}) 出现极高置信度({r['confidence']}%)的买入信号，请关注！",
                            related_code=r['code']
                        )

            return JsonResponse({'code': 200, 'data': results})
        except Exception as e:
            print(f"Analysis Error: {e}")
            return JsonResponse({'code': 500, 'msg': str(e)})
    return JsonResponse({'code': 405})


@csrf_exempt
def api_stock_detail(request):
    """获取详情页K线数据及买卖点标注"""
    code = request.GET.get('code', '000001')

    # 获取数据
    qs = StockDaily.objects.filter(ts_code=code).order_by('trade_date')
    if not qs.exists():
        return JsonResponse({'code': 404, 'msg': '未找到该股票数据'})

    data = list(qs.values('trade_date', 'open_price', 'close_price', 'low_price', 'high_price', 'vol'))
    df = pd.DataFrame(data)

    # 重命名列以适配算法
    df.rename(columns={'open_price': 'open', 'close_price': 'close', 'high_price': 'high', 'low_price': 'low'},
              inplace=True)

    # 计算指标
    df = calculate_indicators(df)

    # 生成买卖点信号 (matcher.py)
    signals = analyze_kline_signals(df)

    return JsonResponse({
        'code': 200,
        'data': {
            'dates': df['trade_date'].apply(lambda x: x.strftime('%Y-%m-%d')).tolist(),
            'values': df[['open', 'close', 'low', 'high', 'vol']].values.tolist(),
            'mas': {
                'MA5': df['MA5'].fillna(0).tolist(),
                'MA20': df['MA20'].fillna(0).tolist()
            },
            'signals': signals  # 前端用于在K线图上画点
        }
    })


# ==========================================
# 4. 收藏与交易 API
# ==========================================
@csrf_exempt
def api_fav_add(request):
    """添加/移除收藏"""
    if request.method == 'POST':
        body = json.loads(request.body)
        code = body.get('code')
        group = body.get('group', 'DEFAULT')

        # 如果已存在则不做操作（或者你可以改成 toggle 逻辑）
        # 这里实现简单的“添加”逻辑
        obj, created = FavoriteStock.objects.get_or_create(
            ts_code=code,
            defaults={'group': group}
        )
        if not created:
            # 如果已存在，更新分组
            obj.group = group
            obj.save()

        return JsonResponse({'code': 200, 'msg': '已加入收藏'})
    return JsonResponse({'code': 405})


def api_fav_list(request):
    """获取收藏列表"""
    favs = list(FavoriteStock.objects.all().values('ts_code', 'group', 'notes'))
    return JsonResponse({'code': 200, 'data': favs})


@csrf_exempt
def api_place_order(request):
    """模拟交易下单"""
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            TradeRecord.objects.create(
                ts_code=body['code'],
                trade_date=datetime.date.today(),
                trade_type=body.get('type', 'BUY'),
                price=float(body['price']),
                volume=int(body.get('volume', 100)),
                strategy_name=body.get('strategy', '手动交易')
            )
            return JsonResponse({'code': 200, 'msg': '交易成功'})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': str(e)})
    return JsonResponse({'code': 405})


def api_trade_data(request):
    """获取交易历史流水"""
    records = TradeRecord.objects.all().order_by('-create_time')
    data = []
    for r in records:
        data.append({
            'date': r.trade_date.strftime('%Y-%m-%d'),
            'code': r.ts_code,
            'type': r.trade_type,
            'price': r.price,
            'volume': r.volume,
            'strategy': r.strategy_name
        })
    return JsonResponse({'code': 200, 'data': data})


# ==========================================
# 5. 预测与消息 API
# ==========================================
def api_check_messages(request):
    """获取最新未读消息"""
    msgs = list(SystemMessage.objects.filter(is_read=False).order_by('-create_time').values()[:5])
    # 简单的“已读”处理逻辑可以在前端点开时再触发，这里仅返回
    return JsonResponse({'code': 200, 'data': msgs})


@csrf_exempt
def api_run_prediction(request):
    """运行AI趋势预测"""
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            code = body.get('code')
            res = run_lstm_prediction(code)
            return JsonResponse({'code': 200, 'data': res})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': str(e)})
    return JsonResponse({'code': 405})


@csrf_exempt
def api_run_backtest(request):
    """运行历史回测"""
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            code = body.get('code')
            res = run_backtest_strategy(code)
            if res:
                return JsonResponse({'code': 200, 'data': res})
            else:
                return JsonResponse({'code': 404, 'msg': '数据不足，无法回测'})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': str(e)})
    return JsonResponse({'code': 405})