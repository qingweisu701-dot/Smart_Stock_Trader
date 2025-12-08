import numpy as np
import pandas as pd
from fastdtw import fastdtw
from data_engine.models import StockDaily, StockBasic

# ==========================================
# 1. 形态定义 (20种经典形态 - 知识库)
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
# 2. 基础计算与指标
# ==========================================
def normalize_series(series):
    series = np.array(series)
    if np.std(series) == 0: return series
    return (series - np.mean(series)) / np.std(series)


def calculate_indicators(df):
    if 'close' not in df.columns: return df
    # MA
    df['MA5'] = df['close'].rolling(5).mean()
    df['MA10'] = df['close'].rolling(10).mean()
    df['MA20'] = df['close'].rolling(20).mean()
    # MACD
    exp12 = df['close'].ewm(span=12, adjust=False).mean()
    exp26 = df['close'].ewm(span=26, adjust=False).mean()
    df['DIF'] = exp12 - exp26
    df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    return df.fillna(0)


def analyze_kline_signals(df):
    """生成带索引的详细买卖点信号 (供详情页使用)"""
    signals = []
    if len(df) < 5: return signals

    for i in range(2, len(df)):
        curr = df.iloc[i]
        prev = df.iloc[i - 1]

        # 1. 均线金叉 (买)
        if prev['MA5'] < prev['MA10'] and curr['MA5'] > curr['MA10']:
            signals.append({'idx': i, 'type': 'BUY', 'msg': 'MA金叉'})
        # 2. 均线死叉 (卖)
        if prev['MA5'] > prev['MA10'] and curr['MA5'] < curr['MA10']:
            signals.append({'idx': i, 'type': 'SELL', 'msg': 'MA死叉'})
        # 3. MACD金叉 (买)
        if prev['DIF'] < prev['DEA'] and curr['DIF'] > curr['DEA']:
            signals.append({'idx': i, 'type': 'BUY', 'msg': 'MACD金叉'})
        # 4. 乌云盖顶 (卖)
        if prev['close'] > prev['open'] and curr['close'] < curr['open']:
            mid = (prev['close'] + prev['open']) / 2
            if curr['open'] > prev['close'] and curr['close'] < mid:
                signals.append({'idx': i, 'type': 'SELL', 'msg': '乌云盖顶'})
        # 5. 长剑指天 (卖)
        body = abs(curr['close'] - curr['open'])
        upper = curr['high'] - max(curr['close'], curr['open'])
        if upper > 2 * body and body > 0:
            signals.append({'idx': i, 'type': 'SELL', 'msg': '长剑指天'})

    return signals


# ==========================================
# 3. 核心全市场扫描 (筛选 + 匹配 + 评分)
# ==========================================
def run_analysis_core(target_pattern_data=None, filters=None):
    # 1. 准备形态数据
    has_pattern = target_pattern_data is not None and len(target_pattern_data) > 3
    if has_pattern: norm_target = normalize_series(target_pattern_data)

    all_stocks = StockBasic.objects.all()
    results = []

    filters = filters or {}
    min_score = float(filters.get('minScore', 60))
    target_cap = filters.get('marketCap', '')
    target_sector = filters.get('sector', '')
    strategies = filters.get('strategies', [])

    # 🔥【找回】OHLC 四维价格筛选
    f_min_open = float(filters.get('minOpen') or 0)
    f_max_open = float(filters.get('maxOpen') or 99999)
    f_min_close = float(filters.get('minClose') or 0)
    f_max_close = float(filters.get('maxClose') or 99999)
    f_min_high = float(filters.get('minHigh') or 0)  # 新增
    f_max_low = float(filters.get('maxLow') or 99999)  # 新增

    for stock in all_stocks:
        # --- A. 市值筛选 (逻辑找回) ---
        m_cap = stock.market_cap or 0
        # 大盘: >200亿, 中盘: 50-200亿, 小盘: <50亿
        if target_cap == 'SMALL' and m_cap >= 50: continue
        if target_cap == 'MID' and (m_cap < 50 or m_cap > 200): continue
        if target_cap == 'LARGE' and m_cap <= 200: continue

        if target_sector and target_sector not in (stock.industry or ''): continue

        # --- B. 获取行情 ---
        qs = StockDaily.objects.filter(ts_code=stock.ts_code).order_by('-trade_date')[:60]
        data = list(qs.values('trade_date', 'open_price', 'close_price', 'high_price', 'low_price', 'vol'))
        if len(data) < 20: continue

        df = pd.DataFrame(data[::-1])
        df.rename(columns={'open_price': 'open', 'close_price': 'close', 'high_price': 'high', 'low_price': 'low'},
                  inplace=True)

        curr = df.iloc[-1]

        # 🔥【找回】价格筛选执行
        if not (f_min_open <= curr['open'] <= f_max_open): continue
        if not (f_min_close <= curr['close'] <= f_max_close): continue
        if not (f_min_high <= curr['high']): continue  # 最高价筛选
        if not (curr['low'] <= f_max_low): continue  # 最低价筛选

        # ... (C. 指标计算, D. 形态匹配, E. 评分 - 保持不变) ...
        # (为了篇幅，这里假设中间逻辑与之前一致，请确保不要删除)

        df = calculate_indicators(df)
        all_signals = analyze_kline_signals(df)
        last_idx = len(df) - 1
        today_signals = [s['msg'] for s in all_signals if s['idx'] == last_idx]

        if 'MA_GOLD' in strategies and 'MA金叉' not in today_signals: continue
        if 'MACD_GOLD' in strategies and 'MACD金叉' not in today_signals: continue

        dtw_score = 0
        match_data = []
        if has_pattern:
            window = len(target_pattern_data)
            if len(df) >= window:
                segment = df['close'].iloc[-window:].values
                dist, _ = fastdtw(norm_target, normalize_series(segment), dist=lambda x, y: abs(x - y))
                dtw_score = max(0, 100 - dist * 2)
                match_data = segment.tolist()

        final_score = dtw_score if has_pattern else 60
        if 'MA金叉' in today_signals: final_score += 10
        if final_score < min_score: continue

        confidence = min(99, max(10, 50 + (final_score - 60) * 0.6))

        results.append({
            'code': stock.ts_code,
            'name': stock.name,
            'price': round(curr['close'], 2),
            'score': round(final_score, 1),
            'confidence': round(confidence, 1),
            'signals': today_signals,
            'match_data': match_data,
            'match_type': 'BUY'
        })

    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:30]