from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import StockDaily, StockBasic, UserPattern, FavoriteStock, TradeRecord, SystemMessage
from algorithms.matcher import run_analysis_core, PRESET_PATTERNS
import json, datetime
import pandas as pd


# ... (保留页面渲染函数) ...
def page_pattern_manage(request): return render(request, 'pattern_manage.html')


def page_analysis(request): return render(request, 'analysis.html')


# ... (其他页面) ...

@csrf_exempt
def api_pattern_save(request):
    if request.method == 'POST':
        body = json.loads(request.body)
        p_type = body.get('type')  # DRAW 或 KLINE
        data = body.get('data')

        # 存库
        if p_type == 'DRAW':
            # 数组转字符串
            data_str = ",".join(map(str, data))
        else:
            # K线对象数组转JSON字符串
            data_str = json.dumps(data)

        UserPattern.objects.create(
            name=body['name'],
            source_type=p_type,
            description=body.get('desc', ''),
            data_points=data_str
        )
        return JsonResponse({'code': 200})


@csrf_exempt
def api_run_analysis(request):
    if request.method == 'POST':
        body = json.loads(request.body)
        # 获取前端传来的参数
        p_data = body.get('pattern_data')
        filters = body.get('filters', {})

        # 调用核心算法
        # 注意：run_analysis_core 需要你在 matcher.py 里根据新需求微调
        # 这里仅做示例连接
        results = run_analysis_core(p_data, filters)

        return JsonResponse({'code': 200, 'data': results})


# ... (api_pattern_list 等其他接口稍微修改以返回 type 字段) ...
@csrf_exempt
def api_pattern_list(request):
    # 预设
    presets = []
    for k, v in PRESET_PATTERNS.items():
        presets.append({'id': k, 'name': v['desc'], 'data': v['data'], 'type': v['type']})

    # 用户
    users = []
    for u in UserPattern.objects.all():
        # 如果是KLINE类型，解析JSON
        data = []
        if u.source_type == 'KLINE':
            try:
                data = json.loads(u.data_points)
            except:
                pass
        else:
            data = [float(x) for x in u.data_points.split(',')]

        users.append({'id': u.id, 'name': u.name, 'data': data, 'type': 'CUSTOM'})

    return JsonResponse({'code': 200, 'data': {'presets': presets, 'users': users}})

# ... (api_stock_detail, api_place_order 等保持逻辑，记得加上价格筛选的传递) ...