import numpy as np
import pandas as pd
from fastdtw import fastdtw
from data_engine.models import StockDaily, StockBasic


# ==========================================
# 1. 基础工具函数
# ==========================================

def normalize_series(series):
    series = np.array(series)
    if np.std(series) == 0: return series
    return (series - np.mean(series)) / np.std(series)


def calculate_technical_indicators(df):
    """计算指标: MACD, MA, RSI, KDJ"""
    if 'close' not in df.columns:
        return df

    # MA 均线系统
    df['MA5'] = df['close'].rolling(window=5).mean()
    df['MA10'] = df['close'].rolling(window=10).mean()
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

    # KDJ (简单版实现)
    low_list = df['low'].rolling(9, min_periods=9).min()
    high_list = df['high'].rolling(9, min_periods=9).max()
    rsv = (df['close'] - low_list) / (high_list - low_list) * 100
    df['K'] = rsv.ewm(com=2, adjust=False).mean()
    df['D'] = df['K'].ewm(com=2, adjust=False).mean()
    df['J'] = 3 * df['K'] - 2 * df['D']

    return df.fillna(0)


# ==========================================
# 2. 策略动态检查器
# ==========================================
def check_strategies(df, strategy_list, logic_type='AND'):
    if not strategy_list:
        return True, "无策略限制"

    if len(df) < 2:
        return False, "数据不足"

    curr = df.iloc[-1]
    prev = df.iloc[-2]

    results = []
    labels = []

    # 1. MACD 金叉
    if 'MACD_GOLD' in strategy_list:
        hit = prev['DIF'] < prev['DEA'] and curr['DIF'] > curr['DEA']
        results.append(hit)
        if hit: labels.append("MACD金叉")

    # 2. 均线多头
    if 'MA_LONG' in strategy_list:
        hit = curr['close'] > curr['MA5'] > curr['MA20']
        results.append(hit)
        if hit: labels.append("均线多头")

    # 3. RSI 超卖
    if 'RSI_LOW' in strategy_list:
        hit = curr['RSI'] < 30
        results.append(hit)
        if hit: labels.append("RSI超卖")

    if not results: return True, "无有效策略"

    if logic_type == 'AND':
        final_pass = all(results)
    else:
        final_pass = any(results)

    return final_pass, ",".join(labels) if labels else "不满足策略"


# ==========================================
# 3. 核心匹配逻辑 (支持返回股票名称)
# ==========================================

def run_pattern_matching(user_pattern_prices, mode='BUY', filters=None):
    # 1. 检查形态输入
    has_pattern = False
    norm_user_pattern = []
    pattern_len = 0
    if user_pattern_prices and len(user_pattern_prices) >= 3:
        has_pattern = True
        norm_user_pattern = normalize_series(user_pattern_prices)
        pattern_len = len(user_pattern_prices)

    # 2. 获取基础股票列表 (包含名称、市值等)
    all_stocks = StockBasic.objects.all()
    results = []

    # 解析筛选条件
    strategy_list = filters.get('strategies', []) if filters else []
    logic_type = filters.get('logic', 'OR') if filters else 'OR'
    query_code = filters.get('codeQuery', '') if filters else ''
    min_score = float(filters.get('minScore', 60)) if filters else 60

    target_sector = filters.get('sector') if filters else None
    target_cap = filters.get('marketCap') if filters else None

    for stock in all_stocks:
        code = stock.ts_code
        name = stock.name  # 🔥 获取股票名称

        # --- 0. 基础硬筛选 ---

        # 0.1 代码/名称过滤 (支持搜代码或搜名字)
        if query_code:
            if (query_code not in code) and (query_code not in name):
                continue

        # 0.2 行业过滤
        # 简单匹配：如果 filters.sector 是 'Finance'，而 stock.industry 是 '银行'，需自行建立映射
        # 这里为了演示，假设必须完全匹配数据库里的 industry 字段
        # if target_sector and target_sector != stock.industry: continue

        # 0.3 市值过滤
        m_cap = stock.market_cap or 0
        if target_cap:
            if target_cap == 'SMALL' and m_cap >= 100: continue
            if target_cap == 'MID' and (m_cap < 100 or m_cap > 500): continue
            if target_cap == 'LARGE' and m_cap <= 500: continue

        # --- 1. 获取日线数据 ---
        qs = StockDaily.objects.filter(ts_code=code).order_by('trade_date')
        data = list(qs.values('trade_date', 'open_price', 'close_price', 'high_price', 'low_price'))
        df = pd.DataFrame(data)

        if len(df) < 20: continue  # 数据太少忽略

        if not df.empty:
            df.rename(columns={'open_price': 'open', 'close_price': 'close', 'high_price': 'high', 'low_price': 'low'},
                      inplace=True)

        # --- 1. 计算指标 (全量计算) ---
        df = calculate_technical_indicators(df)
        curr = df.iloc[-1]

        # --- 2. 价格区间筛选 ---
        if filters:
            min_p = float(filters.get('minPrice') or 0)
            max_p = float(filters.get('maxPrice') or 99999)
            if not (min_p <= curr['close'] <= max_p): continue

        # --- 3. 策略检查 ---
        is_triggered, trigger_msg = check_strategies(df, strategy_list, logic_type)
        strategy_score = 40 if is_triggered else 0 if strategy_list else 0

        # --- 4. 形态相似度 (DTW) ---
        dtw_score = 0
        match_data_show = []
        match_dates_show = []

        if has_pattern and len(df) > pattern_len:
            pre_signal_prices = df['close'].iloc[-pattern_len:].values
            pre_signal_dates = df['trade_date'].iloc[-pattern_len:].tolist()
            norm_stock_pattern = normalize_series(pre_signal_prices)
            distance, _ = fastdtw(norm_user_pattern, norm_stock_pattern, dist=lambda x, y: abs(x - y))
            base_score = 60 if strategy_list else 100
            dtw_score = base_score / (1 + distance)
            match_data_show = pre_signal_prices.tolist()
            match_dates_show = [d.strftime('%Y-%m-%d') for d in pre_signal_dates]
            trigger_msg_final = trigger_msg if is_triggered else "形态匹配"
        else:
            match_data_show = df['close'].iloc[-20:].values.tolist()
            match_dates_show = [d.strftime('%Y-%m-%d') for d in df['trade_date'].iloc[-20:].tolist()]
            trigger_msg_final = trigger_msg if is_triggered else "基础筛选"

        final_score = dtw_score + strategy_score
        if not has_pattern and not strategy_list: final_score = 60

        if final_score < min_score: continue

        results.append({
            'code': code,
            'name': name,  # 🔥 必须返回名字
            'score': round(final_score, 2),
            'score_breakdown': {'dtw': round(dtw_score, 2), 'strategy': strategy_score},
            'trigger': trigger_msg_final,
            'price': round(curr['close'], 2),
            'date': curr['trade_date'].strftime('%Y-%m-%d'),
            'match_data': match_data_show,
            'match_range': f"{match_dates_show[0]} ~ {match_dates_show[-1]}" if match_dates_show else ""
        })

    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:10]