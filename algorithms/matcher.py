import numpy as np
import pandas as pd
from fastdtw import fastdtw
from data_engine.models import StockDaily


# ==========================================
# 1. 基础工具函数
# ==========================================

def normalize_series(series):
    """Z-Score 标准化"""
    series = np.array(series)
    if np.std(series) == 0: return series
    return (series - np.mean(series)) / np.std(series)


def calculate_technical_indicators(df):
    """
    计算关键指标 (MACD, MA, RSI)
    必须执行这一步，否则后续判断金叉死叉时会报 'DIF' 错误
    """
    # 1. 计算均线
    df['MA5'] = df['close'].rolling(window=5).mean()
    df['MA20'] = df['close'].rolling(window=20).mean()

    # 2. 计算 MACD (DIF, DEA)
    exp12 = df['close'].ewm(span=12, adjust=False).mean()
    exp26 = df['close'].ewm(span=26, adjust=False).mean()
    df['DIF'] = exp12 - exp26
    df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()

    # 3. 计算 RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # 填充空值，防止报错
    return df.fillna(0)


# ==========================================
# 2. 核心匹配逻辑
# ==========================================

def run_pattern_matching(user_pattern_prices, mode='BUY', filters=None):
    """
    核心匹配函数 (修复版)
    """
    if not user_pattern_prices or len(user_pattern_prices) < 5:
        return []

    norm_user_pattern = normalize_series(user_pattern_prices)
    pattern_len = len(user_pattern_prices)

    all_codes = StockDaily.objects.values_list('ts_code', flat=True).distinct()
    results = []

    # 模拟的基本面数据 (用于演示筛选)
    mock_stock_info = {
        '000001': {'sector': 'Finance', 'cap': 'LARGE'},
        '600519': {'sector': 'Consumer', 'cap': 'LARGE'},
        '300750': {'sector': 'Energy', 'cap': 'LARGE'},
    }

    for code in all_codes:
        # --- 0. 基础筛选 ---
        if filters:
            stock_sector = mock_stock_info.get(code, {}).get('sector', 'Other')
            if filters.get('sector') and filters['sector'] != stock_sector:
                continue

            stock_cap = mock_stock_info.get(code, {}).get('cap', 'SMALL')
            if filters.get('marketCap') and filters['marketCap'] != stock_cap:
                continue

        # 获取数据
        qs = StockDaily.objects.filter(ts_code=code).order_by('trade_date')
        # 转换为 DataFrame
        df = pd.DataFrame(list(qs.values('trade_date', 'open', 'close', 'high', 'low')))

        # 数据长度检查
        if len(df) < pattern_len + 5:
            continue

        # --- 1. 核心修复点：必须先计算指标！ ---
        df = calculate_technical_indicators(df)

        # 获取最新数据
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        current_price = curr['close']

        # --- 2. 价格区间筛选 ---
        if filters:
            min_p = float(filters.get('minPrice') or 0)
            max_p = float(filters.get('maxPrice') or 99999)
            if not (min_p <= current_price <= max_p):
                continue

        # --- 3. 判断触发信号 ---
        trigger_msg = "纯形态匹配"
        is_triggered = False

        if mode == 'BUY':
            # 这里调用 prev['DIF'] 就不会报错了，因为上面 calculate_technical_indicators 已经算好了
            if prev['DIF'] < prev['DEA'] and curr['DIF'] > curr['DEA']:
                trigger_msg = "MACD金叉"
                is_triggered = True
            elif curr['close'] > curr['MA5'] > curr['MA20']:
                trigger_msg = "均线多头"
                is_triggered = True
            elif prev['RSI'] < 30 and curr['RSI'] > 30:
                trigger_msg = "RSI超卖"
                is_triggered = True

        elif mode == 'SELL':
            if prev['DIF'] > prev['DEA'] and curr['DIF'] < curr['DEA']:
                trigger_msg = "MACD死叉"
                is_triggered = True
            elif curr['close'] < curr['MA20']:
                trigger_msg = "跌破均线"
                is_triggered = True

        # --- 4. 计算形态相似度 (DTW) ---
        pre_signal_prices = df['close'].iloc[-pattern_len:].values
        norm_stock_pattern = normalize_series(pre_signal_prices)

        distance, _ = fastdtw(norm_user_pattern, norm_stock_pattern, dist=lambda x, y: abs(x - y))
        dtw_score = 100 / (1 + distance)

        final_score = dtw_score + (20 if is_triggered else 0)

        results.append({
            'code': code,
            'score': round(final_score, 2),
            'trigger': trigger_msg,
            'price': round(curr['close'], 2),
            'date': curr['trade_date'].strftime('%Y-%m-%d'),
            'match_data': pre_signal_prices.tolist()
        })

    # 排序返回
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:5]