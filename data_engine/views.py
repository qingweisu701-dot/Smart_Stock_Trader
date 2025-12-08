from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
# 🔥 关键：确保引入 PatternFavorite
from .models import StockDaily, StockBasic, UserPattern, FavoriteStock, TradeRecord, SystemMessage, PatternFavorite
from algorithms.matcher import run_analysis_core, PRESET_PATTERNS, analyze_kline_signals, calculate_indicators
from algorithms.predictor import run_lstm_prediction
from algorithms.backtest import run_backtest_strategy
import json, datetime
import pandas as pd
import numpy as np


# ==================== 页面渲染 ====================
def page_pattern_draw(request):
    """图形绘制页 (手绘)"""
    return render(request, 'pattern_manage.html')


def page_pattern_list(request):
    """图形清单页"""
    # 暂时复用 pattern_lab 或新建，这里指向 pattern_lab 保证不报错
    return render(request, 'pattern_lab.html')


def page_pattern_lab(request):
    """图形管理实验室 (新版)"""
    return render(request, 'pattern_lab.html')


def page_analysis_scan(request):
    """市场扫描页"""
    return render(request, 'analysis_scan.html')


def page_analysis_fav(request):
    """我的观察仓页"""
    return render(request, 'analysis_fav.html')


def page_decision_center(request):
    """决策中心页"""
    return render(request, 'decision_center.html')


def page_trade_history(request):
    """交易流水页"""
    return render(request, 'trade_history.html')


def page_prediction(request):
    """(兼容旧路由)"""
    return render(request, 'prediction_ai.html')


def page_prediction_ai(request):
    return render(request, 'prediction_ai.html')


def page_prediction_backtest(request):
    return render(request, 'prediction_backtest.html')


# ==================== 1. 图形管理 API ====================

@csrf_exempt
def api_pattern_list(request):
    """获取形态列表（含收藏状态）"""
    try:
        # 获取用户收藏的形态ID集合
        fav_qs = PatternFavorite.objects.all()
        # 格式化为 "PRESET:five_waves" 或 "USER:12"
        fav_ids = set([f"{f.pattern_type}:{f.pattern_id}" for f in fav_qs])

        # 1. 预设形态
        presets = []
        for k, v in PRESET_PATTERNS.items():
            is_fav = f"PRESET:{k}" in fav_ids
            presets.append({
                'id': k,
                'name': v['desc'],
                'data': v['data'],
                'type': v['type'],
                'is_fav': is_fav
            })

        # 2. 用户自定义
        users = []
        for u in UserPattern.objects.all():
            try:
                data = json.loads(u.data_points) if u.source_type == 'KLINE' else [float(x) for x in
                                                                                   u.data_points.split(',')]
                is_fav = f"USER:{u.id}" in fav_ids
                users.append({
                    'id': u.id,
                    'name': u.name,
                    'data': data,
                    'type': 'CUSTOM',
                    'desc': u.description,
                    'is_fav': is_fav
                })
            except:
                pass

        return JsonResponse({'code': 200, 'data': {'presets': presets, 'users': users}})
    except Exception as e:
        print(f"Error in api_pattern_list: {e}")
        return JsonResponse({'code': 500, 'msg': str(e)})


@csrf_exempt
def api_pattern_fav_toggle(request):
    """切换形态收藏状态"""
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            pid = str(body.get('id'))
            ptype = body.get('type')  # PRESET 或 USER

            # 这里的 type 前端传过来可能是 'CUSTOM'，数据库里存的是 'USER'，做个映射
            db_type = 'USER' if ptype == 'CUSTOM' else ptype
            if ptype == 'PRESET': db_type = 'PRESET'

            obj, created = PatternFavorite.objects.get_or_create(pattern_id=pid, pattern_type=db_type)
            if not created:
                obj.delete()  # 存在则删除（取消收藏）
                return JsonResponse({'code': 200, 'msg': '已取消收藏', 'status': False})
            return JsonResponse({'code': 200, 'msg': '收藏成功', 'status': True})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': str(e)})
    return JsonResponse({'code': 405})


@csrf_exempt
def api_pattern_save(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            p_type = body.get('type', 'DRAW')
            data = body.get('data')
            data_str = json.dumps(data) if p_type == 'KLINE' else ",".join(map(str, data))

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


@csrf_exempt
def api_pattern_delete(request):
    if request.method == 'POST':
        try:
            UserPattern.objects.filter(id=json.loads(request.body)['id']).delete()
            return JsonResponse({'code': 200, 'msg': '删除成功'})
        except:
            return JsonResponse({'code': 500})
    return JsonResponse({'code': 405})


@csrf_exempt
def api_analyze_pattern_trend(request):
    # 简单模拟趋势分析
    return JsonResponse({'code': 200, 'data': {'trend': 'BUY', 'msg': 'AI分析完成'}})


# ==================== 2. 市场分析 API ====================

@csrf_exempt
def api_run_analysis(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            # 调用算法核心
            results = run_analysis_core(body.get('pattern_data'), body.get('filters', {}))
            return JsonResponse({'code': 200, 'data': results})
        except Exception as e:
            print(f"Analysis Error: {e}")
            return JsonResponse({'code': 500, 'msg': str(e)})
    return JsonResponse({'code': 405})


@csrf_exempt
def api_stock_detail(request):
    """详情页数据"""
    code = request.GET.get('code')
    qs = StockDaily.objects.filter(ts_code=code).order_by('trade_date')
    if not qs.exists(): return JsonResponse({'code': 404})

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
            'mas': {'MA5': df['MA5'].tolist(), 'MA20': df['MA20'].tolist()},
            'signals': signals
        }
    })


# ==================== 3. 收藏与交易 API ====================

def api_fav_list(request):
    # 增强：返回名称
    favs = FavoriteStock.objects.all()
    data = []
    for f in favs:
        name = f.ts_code
        try:
            name = StockBasic.objects.get(ts_code=f.ts_code).name
        except:
            pass
        data.append({'code': f.ts_code, 'name': name, 'group': f.group, 'notes': f.notes})
    return JsonResponse({'code': 200, 'data': data})


@csrf_exempt
def api_fav_add(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            FavoriteStock.objects.get_or_create(ts_code=body['code'], defaults={'group': body.get('group', 'DEFAULT')})
            return JsonResponse({'code': 200})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': str(e)})
    return JsonResponse({'code': 405})


@csrf_exempt
def api_place_order(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            TradeRecord.objects.create(
                ts_code=body['code'], trade_date=datetime.date.today(),
                trade_type=body.get('type', 'BUY'), price=body['price'], volume=body['volume']
            )
            return JsonResponse({'code': 200, 'msg': '交易成功'})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': str(e)})
    return JsonResponse({'code': 405})


def api_trade_data(request):
    records = TradeRecord.objects.all().order_by('-create_time')
    data = [{'date': r.trade_date.strftime('%Y-%m-%d'), 'code': r.ts_code, 'type': r.trade_type,
             'price': r.price, 'volume': r.volume, 'strategy': r.strategy_name} for r in records]
    return JsonResponse({'code': 200, 'data': data})


# ==================== 4. 预测与消息 API ====================

@csrf_exempt
def api_run_prediction(request):
    if request.method == 'POST':
        try:
            res = run_lstm_prediction(json.loads(request.body).get('code'))
            return JsonResponse({'code': 200, 'data': res})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': str(e)})
    return JsonResponse({'code': 405})


@csrf_exempt
def api_run_backtest(request):
    if request.method == 'POST':
        try:
            res = run_backtest_strategy(json.loads(request.body).get('code'))
            return JsonResponse({'code': 200, 'data': res})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': str(e)})
    return JsonResponse({'code': 405})


def api_check_messages(request):
    try:
        msgs = list(SystemMessage.objects.filter(is_read=False).values()[:5])
        return JsonResponse({'code': 200, 'data': msgs})
    except:
        return JsonResponse({'code': 200, 'data': []})


# ==================== 5. 旧接口兼容 ====================
def get_kline_data(request):
    # 简单的 K 线接口，用于旧版兼容
    return api_stock_detail(request)


@csrf_exempt
def api_pattern_save(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            p_type = body.get('type', 'DRAW')
            data = body.get('data')

            # 🔥 修复：K线存 JSON，趋势线存逗号分隔
            if p_type == 'KLINE':
                data_str = json.dumps(data)
            else:
                data_str = ",".join(map(str, data))

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