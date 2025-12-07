import numpy as np
import pandas as pd
from fastdtw import fastdtw
from data_engine.models import StockDaily


# ==========================================
# 1. 基础工具函数
# ==========================================

def normalize_series(series):
    series = np.array(series)
    if np.std(series) == 0: return series
    return (series - np.mean(series)) / np.std(series)


def calculate_technical_indicators(df):
    """计算指标: MACD, MA, RSI"""
    # MA
    df['MA5'] = df['close'].rolling(window=5).mean()
    df['MA20'] = df['close'].rolling(window=20).mean()

    # MACD
    exp12 = df['close'].ewm(span=12, adjust=False).mean()
    exp26 = df['close'].ewm(span=26, adjust=False).mean()
    df['DIF'] = exp12 - exp26
    df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()

    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    return df.fillna(0)


# ==========================================
# 2. 策略动态检查器 (核心新增)
# ==========================================
def check_strategies(df, strategy_list, logic_type='AND'):
    """
    动态检查策略组合
    :param strategy_list: ['MACD_GOLD', 'RSI_LOW', ...]
    :param logic_type: 'AND' (全满足) / 'OR' (满足任一)
    """
    if not strategy_list:
        return True, "无策略限制"

    curr = df.iloc[-1]
    prev = df.iloc[-2]

    # 定义所有支持的原子策略逻辑
    results = []
    labels = []

    # 1. MACD 金叉
    if 'MACD_GOLD' in strategy_list:
        hit = prev['DIF'] < prev['DEA'] and curr['DIF'] > curr['DEA']
        results.append(hit)
        if hit: labels.append("MACD金叉")

    # 2. MACD 死叉
    if 'MACD_DEAD' in strategy_list:
        hit = prev['DIF'] > prev['DEA'] and curr['DIF'] < curr['DEA']
        results.append(hit)
        if hit: labels.append("MACD死叉")

    # 3. 均线多头 (价格 > MA5 > MA20)
    if 'MA_LONG' in strategy_list:
        hit = curr['close'] > curr['MA5'] > curr['MA20']
        results.append(hit)
        if hit: labels.append("均线多头")

    # 4. 均线空头 (价格 < MA5 < MA20)
    if 'MA_SHORT' in strategy_list:
        hit = curr['close'] < curr['MA5'] < curr['MA20']
        results.append(hit)
        if hit: labels.append("均线空头")

    # 5. RSI 超卖 (<30)
    if 'RSI_LOW' in strategy_list:
        hit = curr['RSI'] < 30
        results.append(hit)
        if hit: labels.append("RSI超卖")

    # 6. RSI 超买 (>70)
    if 'RSI_HIGH' in strategy_list:
        hit = curr['RSI'] > 70
        results.append(hit)
        if hit: labels.append("RSI超买")

    # 逻辑判定
    if not results: return True, "无有效策略"

    if logic_type == 'AND':
        final_pass = all(results)  # 必须全部为 True
    else:  # OR
        final_pass = any(results)  # 只要有一个 True

    return final_pass, ",".join(labels) if labels else "不满足策略"


# ==========================================
# 3. 核心匹配逻辑
# ==========================================

def run_pattern_matching(user_pattern_prices, mode='BUY', filters=None):
    """
    filters 结构扩展:
    {
        'sector': ...,
        'strategies': ['MACD_GOLD', ...],  <-- 新增
        'logic': 'AND'/'OR'                <-- 新增
    }
    """
    if not user_pattern_prices or len(user_pattern_prices) < 5:
        return []

    norm_user_pattern = normalize_series(user_pattern_prices)
    pattern_len = len(user_pattern_prices)

    all_codes = StockDaily.objects.values_list('ts_code', flat=True).distinct()
    results = []

    # 模拟基本面
    mock_stock_info = {
        '000001': {'sector': 'Finance', 'cap': 'LARGE'},
        '600519': {'sector': 'Consumer', 'cap': 'LARGE'},
        '300750': {'sector': 'Energy', 'cap': 'LARGE'},
    }

    # 解析高级策略配置
    strategy_list = filters.get('strategies', []) if filters else []
    logic_type = filters.get('logic', 'OR') if filters else 'OR'

    for code in all_codes:
        # --- 0. 基础筛选 ---
        if filters:
            stock_sector = mock_stock_info.get(code, {}).get('sector', 'Other')
            if filters.get('sector') and filters['sector'] != stock_sector: continue

            stock_cap = mock_stock_info.get(code, {}).get('cap', 'SMALL')
            if filters.get('marketCap') and filters['marketCap'] != stock_cap: continue

        # 获取数据
        qs = StockDaily.objects.filter(ts_code=code).order_by('trade_date')
        df = pd.DataFrame(list(qs.values('trade_date', 'open', 'close', 'high', 'low')))

        if len(df) < pattern_len + 5: continue

        # --- 1. 计算技术指标 ---
        df = calculate_technical_indicators(df)
        curr = df.iloc[-1]

        # --- 2. 价格区间筛选 ---
        if filters:
            min_p = float(filters.get('minPrice') or 0)
            max_p = float(filters.get('maxPrice') or 99999)
            if not (min_p <= curr['close'] <= max_p): continue

        # --- 3. 【核心升级】动态策略组合检查 ---
        is_triggered, trigger_msg = check_strategies(df, strategy_list, logic_type)

        # 如果勾选了策略，但没满足，是否过滤？
        # 为了演示效果，我们不直接 continue，而是大幅扣分
        strategy_score = 30 if is_triggered else 0

        # --- 4. 形态相似度 (DTW) ---
        pre_signal_prices = df['close'].iloc[-pattern_len:].values
        norm_stock_pattern = normalize_series(pre_signal_prices)
        distance, _ = fastdtw(norm_user_pattern, norm_stock_pattern, dist=lambda x, y: abs(x - y))
        dtw_score = 100 / (1 + distance)

        # 综合分 = 形态分 + 策略分
        # 如果 is_triggered 为 False，策略分就是 0，总分变低，排名靠后
        final_score = dtw_score + strategy_score

        # 构造返回结果
        results.append({
            'code': code,
            'score': round(final_score, 2),
            'trigger': trigger_msg if is_triggered else "形态匹配",  # 显示触发的策略名
            'price': round(curr['close'], 2),
            'date': curr['trade_date'].strftime('%Y-%m-%d'),
            'match_data': pre_signal_prices.tolist()
        })

    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:5]