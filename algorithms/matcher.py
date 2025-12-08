import numpy as np
import pandas as pd
from fastdtw import fastdtw
from data_engine.models import StockDaily, StockBasic

# ==========================================
# 1. 形态定义 (20种经典形态)
# ==========================================
PRESET_PATTERNS = {
    # --- 📈 10种上涨形态 (买入信号) ---
    'five_waves_up': {'data': [0, 6, 2, 8, 4, 10], 'desc': '五浪上涨(趋势加强)', 'type': 'BUY'},
    'w_bottom': {'data': [10, 0, 5, 0, 10], 'desc': 'W底(双重底)', 'type': 'BUY'},
    'v_reversal': {'data': [10, 0, 10], 'desc': 'V型反转(暴力拉升)', 'type': 'BUY'},
    'n_break': {'data': [0, 8, 5, 10], 'desc': 'N字突破(空中加油)', 'type': 'BUY'},
    'rising_three': {'data': [0, 8, 7, 6, 7, 10], 'desc': '上升三法(中继)', 'type': 'BUY'},
    'morning_star': {'data': [10, 0, 1, 8], 'desc': '早晨之星(见底)', 'type': 'BUY'},
    'red_soldiers': {'data': [0, 3, 6, 10], 'desc': '红三兵(步步高)', 'type': 'BUY'},
    'immortal_guide': {'data': [0, 5, 2, 8], 'desc': '仙人指路(试盘)', 'type': 'BUY'},
    'step_up': {'data': [0, 3, 2, 5, 4, 7, 6, 10], 'desc': '递进式上涨(稳健)', 'type': 'BUY'},
    'multi_cannon': {'data': [0, 8, 4, 10], 'desc': '多方炮(两阳夹一阴)', 'type': 'BUY'},

    # --- 📉 10种下跌形态 (卖出信号) ---
    'm_top': {'data': [0, 10, 5, 10, 0], 'desc': 'M头(双重顶)', 'type': 'SELL'},
    'head_shoulders': {'data': [0, 7, 4, 10, 4, 7, 0], 'desc': '头肩顶', 'type': 'SELL'},
    'dark_cloud': {'data': [0, 8, 10, 5], 'desc': '乌云盖顶', 'type': 'SELL'},
    'shooting_star': {'data': [5, 10, 6, 0], 'desc': '长剑指天(射击之星)', 'type': 'SELL'},
    'evening_star': {'data': [0, 10, 9, 2], 'desc': '黄昏之星', 'type': 'SELL'},
    'three_crows': {'data': [10, 7, 4, 0], 'desc': '三只乌鸦', 'type': 'SELL'},
    'guillotine': {'data': [8, 9, 1], 'desc': '断头铡刀(一阴穿多线)', 'type': 'SELL'},
    'hanging_man': {'data': [5, 2, 5, 1], 'desc': '吊颈线(诱多)', 'type': 'SELL'},
    'high_jump_gap': {'data': [10, 9, 5, 0], 'desc': '高位跳空缺口', 'type': 'SELL'},
    'long_black': {'data': [8, 0], 'desc': '长阴落地(断崖)', 'type': 'SELL'},
}


# ==========================================
# 2. 基础工具函数
# ==========================================

def normalize_series(series):
    """归一化序列"""
    series = np.array(series)
    if np.std(series) == 0:
        return series
    return (series - np.mean(series)) / np.std(series)


def calculate_indicators(df):
    """计算技术指标: MA, MACD, RSI"""
    if 'close' not in df.columns:
        return df

    # MA
    df['MA5'] = df['close'].rolling(window=5).mean()
    df['MA10'] = df['close'].rolling(window=10).mean()
    df['MA20'] = df['close'].rolling(window=20).mean()

    # MACD
    exp12 = df['close'].ewm(span=12, adjust=False).mean()
    exp26 = df['close'].ewm(span=26, adjust=False).mean()
    df['DIF'] = exp12 - exp26
    df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
    df['MACD_Bar'] = (df['DIF'] - df['DEA']) * 2

    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    return df.fillna(0)


def analyze_kline_signals(df):
    """
    单K线/组合形态识别 (原名 check_kline_patterns，已修正为 analyze_kline_signals)
    返回: 一个包含信号信息的列表，例如 [{'idx': 10, 'type': 'SELL', 'msg': '乌云盖顶'}]
    """
    signals = []  # 这里返回详细对象，用于前端绘图
    simple_signals = []  # 这里返回字符串列表，用于后端评分

    if len(df) < 3:
        return signals  # 注意：views.py 期望返回详细对象列表，run_analysis_core 期望字符串列表，这里需要兼容

    # 我们主要逻辑是为 run_analysis_core 提供字符串列表
    # 但 views.py 里的 api_stock_detail 需要详细对象
    # 为了兼容，我们这里统一返回 "字符串列表" 给 run_analysis_core 使用
    # 对于 api_stock_detail，我们在下面的逻辑中会处理成带索引的对象

    # --- 这是一个通用检测，返回的是最近一天的信号字符串列表 ---

    curr = df.iloc[-1]
    prev = df.iloc[-2]

    # [长剑指天]
    body_len = abs(curr['close'] - curr['open'])
    upper_shadow = curr['high'] - max(curr['close'], curr['open'])
    lower_shadow = min(curr['close'], curr['open']) - curr['low']
    if upper_shadow > 2 * body_len and body_len > 0 and upper_shadow > 2 * lower_shadow:
        simple_signals.append('长剑指天(风险)')

    # [乌云盖顶]
    if prev['close'] > prev['open']:
        mid_point = (prev['open'] + prev['close']) / 2
        if curr['close'] < curr['open'] and curr['open'] > prev['close'] and curr['close'] < mid_point:
            simple_signals.append('乌云盖顶(见顶)')

    # [断头铡刀]
    if curr['close'] < curr['open']:
        if curr['open'] > max(curr['MA5'], curr['MA10'], curr['MA20']) and \
                curr['close'] < min(curr['MA5'], curr['MA10'], curr['MA20']):
            simple_signals.append('断头铡刀(大跌)')

    # [均线多头]
    if curr['close'] > curr['MA5'] > curr['MA10'] > curr['MA20']:
        simple_signals.append('均线多头')

    # [MACD 金叉]
    if prev['DIF'] < prev['DEA'] and curr['DIF'] > curr['DEA']:
        simple_signals.append('MACD金叉')

    return simple_signals


# 为了支持前端详情页的“历史信号标注”，我们需要一个带索引的版本
# 这个函数专门给 views.py 中的 api_stock_detail 使用
# 如果你在 views.py 里是直接 import analyze_kline_signals，那我们需要把上面那个改名，或者让 views.py 调用下面这个
# 鉴于报错是 `cannot import name 'analyze_kline_signals'`，说明 views.py 在找这个名字。
# 我将保留上面的函数名给 核心分析 用。
# 并增加一个 `analyze_kline_signals_with_index` 给详情页用，或者修改 views.py。
# 最简单的办法：修改 analyze_kline_signals 让它对最后一天有效，
# 同时 views.py 里其实有一段逻辑是 `analyze_kline_signals(df)`，我刚才给你的 views.py 里是有的。
# 等等，之前的 views.py 代码里： signals = analyze_kline_signals(df)
# 然后前端用了 signals.map(s => s.idx ... )
# 这说明 views.py 期望的是带索引的列表！

# 🔥 修正方案：重写 analyze_kline_signals，让它返回带索引的列表 (遍历每一天)
# 这样 views.py 开心，run_analysis_core 我们稍微改一下取值即可。

def analyze_kline_signals(df):
    """
    遍历整个 DataFrame，返回所有触发信号的列表
    格式: [{'idx': 12, 'type': 'SELL', 'msg': '乌云盖顶'}, ...]
    """
    signals = []
    if len(df) < 5: return signals

    for i in range(2, len(df)):
        curr = df.iloc[i]
        prev = df.iloc[i - 1]

        # 1. 均线金叉 (买入)
        if prev['MA5'] < prev['MA10'] and curr['MA5'] > curr['MA10']:
            signals.append({'idx': i, 'type': 'BUY', 'msg': 'MA金叉'})

        # 2. 均线死叉 (卖出)
        if prev['MA5'] > prev['MA10'] and curr['MA5'] < curr['MA10']:
            signals.append({'idx': i, 'type': 'SELL', 'msg': 'MA死叉'})

        # 3. 乌云盖顶 (卖出)
        if prev['close'] > prev['open'] and curr['close'] < curr['open']:
            mid = (prev['close'] + prev['open']) / 2
            if curr['open'] > prev['close'] and curr['close'] < mid:
                signals.append({'idx': i, 'type': 'SELL', 'msg': '乌云盖顶'})

        # 4. 长剑指天 (卖出)
        body = abs(curr['close'] - curr['open'])
        upper = curr['high'] - max(curr['close'], curr['open'])
        if upper > 2 * body and body > 0:
            signals.append({'idx': i, 'type': 'SELL', 'msg': '长剑指天'})

    return signals


# ==========================================
# 3. 核心分析函数
# ==========================================

def run_analysis_core(target_pattern_data=None, filters=None):
    """
    核心全市场扫描与匹配函数
    """
    # 1. 准备形态数据
    has_pattern = target_pattern_data is not None and len(target_pattern_data) > 3
    norm_target = []

    if has_pattern:
        norm_target = normalize_series(target_pattern_data)

    # 2. 获取所有股票
    all_stocks = StockBasic.objects.all()
    results = []

    # 解析筛选参数
    filters = filters or {}
    min_score = float(filters.get('minScore', 60))
    target_cap = filters.get('marketCap', '')
    target_sector = filters.get('sector', '')

    # 价格区间筛选
    min_price_filter = float(filters.get('minPrice') or 0)
    max_price_filter = float(filters.get('maxPrice') or 99999)

    # 3. 遍历
    for stock in all_stocks:
        # --- A. 基础条件筛选 ---
        m_cap = stock.market_cap or 0
        if target_cap == 'SMALL' and m_cap >= 100: continue
        if target_cap == 'MID' and (m_cap < 100 or m_cap > 500): continue
        if target_cap == 'LARGE' and m_cap <= 500: continue

        if target_sector and target_sector not in (stock.industry or ''):
            continue

        # --- B. 获取行情 ---
        qs = StockDaily.objects.filter(ts_code=stock.ts_code).order_by('-trade_date')[:60]
        data = list(qs.values('trade_date', 'open_price', 'close_price', 'high_price', 'low_price', 'vol'))

        if len(data) < 20: continue

        df = pd.DataFrame(data[::-1])
        df.rename(columns={'open_price': 'open', 'close_price': 'close', 'high_price': 'high', 'low_price': 'low'},
                  inplace=True)

        current_price = df.iloc[-1]['close']
        if not (min_price_filter <= current_price <= max_price_filter):
            continue

        # --- C. 计算指标 ---
        df = calculate_indicators(df)

        # 获取所有历史信号
        all_signals = analyze_kline_signals(df)
        # 只取最后一天的信号用于评分
        last_idx = len(df) - 1
        current_day_signals = [s['msg'] for s in all_signals if s['idx'] == last_idx]

        # --- D. DTW 匹配 ---
        dtw_score = 0
        match_data = []

        if has_pattern:
            window_len = len(target_pattern_data)
            if len(df) >= window_len:
                segment = df['close'].iloc[-window_len:].values
                dist, _ = fastdtw(norm_target, normalize_series(segment), dist=lambda x, y: abs(x - y))
                dtw_score = max(0, 100 - dist * 2)
                match_data = segment.tolist()
            else:
                dtw_score = 0

        # --- E. 评分 ---
        if has_pattern:
            final_score = dtw_score
        else:
            final_score = 60

        tech_bonus = 0
        if '均线多头' in current_day_signals: tech_bonus += 10
        if 'MACD金叉' in current_day_signals: tech_bonus += 5
        if '长剑指天' in current_day_signals: tech_bonus -= 20
        if '乌云盖顶' in current_day_signals: tech_bonus -= 20

        final_score += tech_bonus

        if final_score < min_score:
            continue

        trend_strength = 0
        if df.iloc[-1]['close'] > df.iloc[-1]['MA20']: trend_strength = 10
        confidence = 50 + (final_score - 60) * 0.5 + trend_strength
        confidence = min(99, max(10, confidence))

        results.append({
            'code': stock.ts_code,
            'name': stock.name,
            'price': round(current_price, 2),
            'score': round(final_score, 1),
            'confidence': round(confidence, 1),
            'signals': current_day_signals,  # 只返回今天的信号名
            'match_data': match_data,
            'industry': stock.industry,
            'market_cap': stock.market_cap,
            'match_type': 'SELL' if tech_bonus < 0 else 'BUY'
        })

    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:30]