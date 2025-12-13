from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import StockDaily, StockBasic, UserPattern, FavoriteStock, TradeRecord, SystemMessage, PatternFavorite, \
    UserStrategy, StockGroup
from algorithms.matcher import run_analysis_core, PRESET_PATTERNS, analyze_kline_signals, calculate_indicators
from algorithms.predictor import run_lstm_prediction
from algorithms.backtest import run_backtest_strategy
from django.core.mail import send_mail
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


def page_prediction_ai(request):
    return render(request, 'prediction_ai.html')


# ==================== 2. 首页仪表盘与监控 API ====================

@csrf_exempt
def api_dashboard_data(request):
    """
    首页数据接口：包含全套模拟指标，用于展示三窗联动效果
    """
    try:
        index_type = request.GET.get('type', '000001.SH')
        # 基础点位映射
        base_map = {
            '000001.SH': 3280,
            '399001.SZ': 10500,
            '399006.SZ': 2150,
            '000300.SH': 3900,
            '000688.SH': 980
        }
        base = base_map.get(index_type, 3000)

        # 1. 生成模拟K线数据
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

        # 2. 转换为 DataFrame 并计算技术指标
        df = pd.DataFrame(data_list)
        # 调用算法层计算指标 (确保 algorithms/matcher.py 中 calculate_indicators 正常)
        df = calculate_indicators(df)

        # 3. 辅助函数：安全转换为 Python 列表 (防 NaN 和 Numpy 类型)
        def sl(col_name):
            if col_name not in df.columns:
                return [0.0] * len(df)
            return [float(x) if not pd.isna(x) else 0.0 for x in df[col_name]]

        # 4. 构造前端需要的 K 线数组 [date, open, close, low, high, vol]
        # 注意：这里我们返回 dates 数组和 values 数组
        kline_values = df[['open', 'close', 'low', 'high', 'vol']].values.tolist()

        # 5. 构造指标字典 (用于前端三窗联动)
        indicators = {
            'MA5': sl('MA5'),
            'MA10': sl('MA10'),
            'MA20': sl('MA20'),
            'K': sl('K'), 'D': sl('D'), 'J': sl('J'),
            'MACD': sl('MACD'), 'DIF': sl('DIF'), 'DEA': sl('DEA'),
            'RSI': sl('RSI')
        }

        # 6. 市场概况与快照数据
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
    策略巡检与消息推送接口
    """
    try:
        # 1. 后台真实策略巡检 (遍历用户开启监控的策略)
        strats = UserStrategy.objects.filter(is_monitoring=True)
        for s in strats:
            # 去重: 如果最近有该策略的未读消息，就不重复发
            if SystemMessage.objects.filter(title__contains=s.name, is_read=False).exists():
                continue

            # 🔥 核心：调用真实算法扫盘
            filters = s.criteria or {}
            target_pattern = None
            
            # 解析可能的形态参数
            if filters.get('patternId'):
                try:
                    pid = filters.get('patternId', '').split(':')[-1]
                    # 尝试从预设或用户库获取形态数据 (这里简单处理，实际应复用逻辑)
                    if pid in PRESET_PATTERNS:
                         target_pattern = PRESET_PATTERNS[pid]['data']
                    else:
                        up = UserPattern.objects.filter(id=pid).first()
                        if up:
                            target_pattern = json.loads(up.data_points) if up.source_type=='KLINE' else [float(x) for x in up.data_points.split(',')]
                except:
                    pass

            # 运行分析 (只取前3个结果作为触发源)
            matches = run_analysis_core(target_pattern, filters)
            
            if matches and len(matches) > 0:
                top_stock = matches[0]
                # 只有当开启消息推送时才创建消息
                if s.notify_msg:
                    SystemMessage.objects.create(
                        title=f"策略命中: {s.name}",
                        content=f"策略【{s.name}】监控到 {len(matches)} 个标的。\n首选: {top_stock['name']}({top_stock['code']}) 相似度 {top_stock['score']}%",
                        related_code=top_stock['code']
                    )
                
                # 发送邮件通知 (暂时关闭)
                # if s.notify_email:
                #     try:
                #         send_mail(
                #             subject=f"【智能投研】策略命中: {s.name}",
                #             message=f"您的策略【{s.name}】监控到 {len(matches)} 个标的。\n"
                #                     f"首选: {top_stock['name']} ({top_stock['code']})\n"
                #                     f"相似度: {top_stock['score']}%\n"
                #                     f"现价: {top_stock['price']}\n\n"
                #                     f"请登录平台查看完整列表。",
                #             from_email='system@smarttrader.com',
                #             recipient_list=['user@example.com'], # 实际应从 request.user 获取
                #             fail_silently=True
                #         )
                #     except:
                #         pass

        # 2. 返回最新 5 条未读消息
        msgs = list(SystemMessage.objects.filter(is_read=False).order_by('-create_time').values()[:5])
        return JsonResponse({'code': 200, 'data': msgs})
    except Exception:
        return JsonResponse({'code': 200, 'data': []})


# ==================== 3. 形态管理 API ====================

@csrf_exempt
def api_pattern_list(request):
    try:
        # 获取收藏列表
        try:
            fav_qs = PatternFavorite.objects.all()
            fav_ids = set([f"{f.pattern_type}:{f.pattern_id}" for f in fav_qs])
        except:
            fav_ids = set()

        presets = []
        # 加载预设形态
        if PRESET_PATTERNS:
            for k, v in PRESET_PATTERNS.items():
                presets.append({
                    'id': k,
                    'name': v['desc'],
                    'data': v['data'],
                    'type': v.get('signal', 'BUY'),
                    'source_type': v.get('type', 'KLINE'),
                    'is_fav': f"PRESET:{k}" in fav_ids
                })

        users = []
        # 加载用户自定义形态
        for u in UserPattern.objects.all():
            try:
                if u.source_type == 'KLINE':
                    data = json.loads(u.data_points)
                else:
                    data = [float(x) for x in u.data_points.split(',')]

                signal = 'BUY'
                if 'SELL' in u.description or '跌' in u.name:
                    signal = 'SELL'

                users.append({
                    'id': u.id,
                    'name': u.name,
                    'data': data,
                    'type': signal,
                    'source_type': u.source_type,
                    'is_fav': f"USER:{u.id}" in fav_ids
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


from algorithms.pattern_backtest import run_pattern_backtest

@csrf_exempt
def api_pattern_verify(request):
    """
    Run historical backtest for a user-drawn pattern.
    """
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            # data could be list of values (DRAW) or list of dicts (KLINE)
            p_data = body.get('data') 
            
            # Pre-process data to list of close prices if it's KLINE
            target_series = []
            if isinstance(p_data, list):
                if len(p_data) > 0:
                    if isinstance(p_data[0], dict):
                        target_series = [x['close'] for x in p_data]
                    else:
                        target_series = p_data
            
            if not target_series:
                 return JsonResponse({'code': 500, 'msg': '无效的数据'})

            result = run_pattern_backtest(target_series, limit_matches=100)
            return JsonResponse({'code': 200, 'data': result['metrics'], 'matches': result['matches']})
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'code': 500, 'msg': str(e)})
            
    return JsonResponse({'code': 405})


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
def api_profit_breakdown(request):
    try:
        from django.db.models import Sum, Count, F
        
        # 简单聚合：按代码分组统计
        # 注意：这里假设 TradeRecord 有 pnl 字段记录了每笔交易的盈亏
        # 如果没有 pnl 数据，需要根据买卖记录实时计算 (复杂)，这里先假设 pnl 字段有值
        # 若 pnl 为空，暂且用 simulation (price * volume * direction) 模拟
        
        # 真实场景应该配对买卖记录计算闭环盈亏。
        # 这里为了演示，我们假设 'SELL' 记录的 (price * volume) - avg_cost 是盈亏
        # 简化处理：返回 TradeRecord 中已有 pnl 的汇总
        
        # 1. 聚合
        records = TradeRecord.objects.values('ts_code').annotate(
            count=Count('id'),
            total_pnl=Sum('pnl')
        )
        
        data = []
        for r in records:
            name = r['ts_code']
            try:
                name = StockBasic.objects.get(ts_code=r['ts_code']).name
            except:
                pass
            
            # 手动计算胜率 (如果有 pnl 数据)
            wins = TradeRecord.objects.filter(ts_code=r['ts_code'], pnl__gt=0).count()
            data.append({
                'code': r['ts_code'],
                'name': name,
                'count': r['count'],
                'total_pnl': round(r['total_pnl'] or 0, 2),
                'win_rate': round(wins / r['count'] * 100, 1) if r['count'] > 0 else 0
            })
            
        return JsonResponse({'code': 200, 'data': data})
    except Exception as e:
        return JsonResponse({'code': 500, 'msg': str(e)})


@csrf_exempt
def api_stock_profit_detail(request):
    try:
        code = request.GET.get('code')
        records = TradeRecord.objects.filter(ts_code=code).order_by('trade_date').values()
        return JsonResponse({'code': 200, 'data': list(records)})
    except Exception as e:
        return JsonResponse({'code': 500, 'msg': str(e)})
@csrf_exempt
def api_stock_detail(request):
    """
    🔥 核心修复：确保指标数据安全返回，并提供仿真数据兜底
    """
    try:
        code = request.GET.get('code', '000001.SZ')
        qs = StockDaily.objects.filter(ts_code=code).order_by('trade_date')

        df = pd.DataFrame()

        # 1. 尝试从数据库获取数据
        if qs.exists():
            data = list(qs.values('trade_date', 'open_price', 'close_price', 'low_price', 'high_price', 'vol'))
            df = pd.DataFrame(data)
            df.rename(columns={'open_price': 'open', 'close_price': 'close', 'high_price': 'high', 'low_price': 'low'},
                      inplace=True)
        else:
            # 2. 如果数据库无数据，生成仿真数据 (防止前端无图)
            dates = pd.date_range(end=datetime.date.today(), periods=60).strftime('%Y-%m-%d').tolist()
            base = 20.0
            mock_data = []
            for d in dates:
                o = base
                c = o * (1 + np.random.uniform(-0.03, 0.03))
                h = max(o, c) * 1.02
                l = min(o, c) * 0.98
                v = int(np.random.randint(5000, 20000))
                mock_data.append({'trade_date': d, 'open': round(o, 2), 'close': round(c, 2), 'high': round(h, 2),
                                  'low': round(l, 2), 'vol': v})
                base = c
            df = pd.DataFrame(mock_data)

        # 3. 计算指标
        df = calculate_indicators(df)
        signals = analyze_kline_signals(df)

        # 4. 安全转换函数
        def sl(col_name):
            if col_name not in df.columns:
                return [0.0] * len(df)
            return [float(x) if not pd.isna(x) else 0.0 for x in df[col_name]]

        return JsonResponse({
            'code': 200,
            'data': {
                'dates': df['trade_date'].apply(lambda x: str(x)[:10]).tolist(),
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
                'basic': {'pe': 22.5, 'industry': '仿真数据' if not qs.exists() else '真实数据'},
                'funds': {'north_in': 5.2, 'main_in': -1.2}
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
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
                is_monitoring=b.get('monitor', False),
                notify_msg=b.get('notify_msg', True),
                notify_email=b.get('notify_email', False)
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
            extra = {
                'tab': b.get('tab', 'basic'),
                'gridBase': b.get('gridBase'), 'gridUp': b.get('gridUp'), 'gridDown': b.get('gridDown'), 'gridVol': b.get('gridVol'),
                'profitType': b.get('profitType'), 'profitVal': b.get('profitVal'),
                'lossType': b.get('lossType'), 'lossVal': b.get('lossVal')
            }
            
            # Determine status: if basic & immediate -> FILLED, else PENDING
            status = 'FILLED' if (b.get('tab') == 'basic' and b.get('triggerValue') == 'IMMEDIATE') else 'PENDING'

            TradeRecord.objects.create(
                ts_code=b['code'],
                trade_date=datetime.date.today(),
                trade_type=b['type'],
                price=float(b['price']) if b.get('price') else 0,
                volume=int(b['volume']),
                trigger_condition=b.get('triggerValue', ''),
                order_validity=b.get('valid', 'day'),
                status=status,
                extra_params=extra
            )
            return JsonResponse({'code': 200})
        except Exception:
            return JsonResponse({'code': 500})
    return JsonResponse({'code': 405})


def api_trade_data(request):
    try:
        data = list(TradeRecord.objects.all().values())
        return JsonResponse({'code': 200, 'data': data})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'code': 500, 'msg': str(e)})


# ==================== 6. 观察仓 API (含 Update) ====================

@csrf_exempt
def api_fav_add(request):
    if request.method == 'POST':
        try:
            FavoriteStock.objects.get_or_create(ts_code=json.loads(request.body)['code'])
            return JsonResponse({'code': 200})
        except Exception:
            return JsonResponse({'code': 500})
    return JsonResponse({'code': 405})


@csrf_exempt
def api_fav_delete(request):
    if request.method == 'POST':
        try:
            FavoriteStock.objects.filter(ts_code=json.loads(request.body)['code']).delete()
            return JsonResponse({'code': 200})
        except Exception:
            return JsonResponse({'code': 500})
    return JsonResponse({'code': 405})


@csrf_exempt
def api_group_rename(request):
    if request.method == 'POST':
        try:
            b = json.loads(request.body)
            old_name = b.get('old_name')
            new_name = b.get('new_name')
            if not old_name or not new_name:
                return JsonResponse({'code': 500, 'msg': '参数缺失'})
            
            # 1. Update Group Name
            StockGroup.objects.filter(name=old_name).update(name=new_name)
            
            # 2. Update Favorites in that group
            FavoriteStock.objects.filter(group=old_name).update(group=new_name)
            
            return JsonResponse({'code': 200})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': str(e)})
    return JsonResponse({'code': 405})


@csrf_exempt
def api_fav_update(request):
    """
    更新观察仓分组
    """
    if request.method == 'POST':
        try:
            b = json.loads(request.body)
            FavoriteStock.objects.filter(ts_code=b['code']).update(group=b['group'])
            return JsonResponse({'code': 200})
        except Exception:
            return JsonResponse({'code': 500})
    return JsonResponse({'code': 405})


def api_fav_list(request):
    favs = FavoriteStock.objects.all()
    data = []
    for f in favs:
        try:
            name = StockBasic.objects.get(ts_code=f.ts_code).name
        except:
            name = f.ts_code
        data.append({'code': f.ts_code, 'name': name, 'group': f.group})
    
    # 获取所有分组
    try:
        db_groups = list(StockGroup.objects.values_list('name', flat=True))
    except Exception:
        db_groups = []
        
    # Ensure defaults are always present and unique
    defaults = ['默认', '观察', '龙头']
    groups = sorted(list(set(defaults + db_groups)))
    # Move defaults to front
    for d in reversed(defaults):
        if d in groups:
            groups.remove(d)
            groups.insert(0, d)
        
    return JsonResponse({'code': 200, 'data': data, 'groups': groups})


@csrf_exempt
def api_group_add(request):
    if request.method == 'POST':
        try:
            name = json.loads(request.body).get('name')
            if name:
                StockGroup.objects.get_or_create(name=name)
            return JsonResponse({'code': 200})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': str(e)})
    return JsonResponse({'code': 405})


@csrf_exempt
def api_group_delete(request):
    if request.method == 'POST':
        try:
            name = json.loads(request.body).get('name')
            StockGroup.objects.filter(name=name).delete()
            # Optional: Move stocks in this group to Default?
            FavoriteStock.objects.filter(group=name).update(group='默认')
            return JsonResponse({'code': 200})
        except Exception:
            return JsonResponse({'code': 500})
    return JsonResponse({'code': 405})


# ==================== 7. AI 预测与回测 ====================

@csrf_exempt
def api_run_prediction(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            # 兼容模型切换参数
            # 如果有 run_predict_dispatch (predictor.py新版)，则使用；否则降级到 run_lstm_prediction
            try:
                from algorithms.predictor import run_predict_dispatch
                res = run_predict_dispatch(body.get('code'), body.get('model', 'LSTM'))
            except ImportError:
                res = run_lstm_prediction(body.get('code'))

            if not res:
                # 兜底数据
                res = {'history_dates': [], 'history_prices': [], 'future_dates': [], 'future_prices': [], 'score': 0,
                       'suggestion': 'HOLD'}
            return JsonResponse({'code': 200, 'data': res})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': str(e)})
    return JsonResponse({'code': 405})


@csrf_exempt
def api_run_backtest(request):
    return JsonResponse({'code': 200, 'data': run_backtest_strategy(json.loads(request.body).get('code'))})