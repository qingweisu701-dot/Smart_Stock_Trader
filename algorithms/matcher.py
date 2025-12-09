import numpy as np
import pandas as pd
from fastdtw import fastdtw
from data_engine.models import StockDaily, StockBasic

# ==========================================
# 1. 完整形态库 (保持不变，确保数据完整)
# ==========================================
PRESET_PATTERNS = {
    'hammer_low': {'type': 'KLINE', 'signal': 'BUY', 'desc': '低位倒锤线',
                   'data': [{'open': 20, 'close': 25, 'low': 20, 'high': 60}]},
    'morning_star': {'type': 'KLINE', 'signal': 'BUY', 'desc': '启明之星',
                     'data': [{'open': 80, 'close': 20, 'low': 15, 'high': 85},
                              {'open': 10, 'close': 15, 'low': 5, 'high': 20},
                              {'open': 25, 'close': 70, 'low': 20, 'high': 75}]},
    'red_soldiers': {'type': 'KLINE', 'signal': 'BUY', 'desc': '红三兵',
                     'data': [{'open': 10, 'close': 30, 'low': 5, 'high': 35},
                              {'open': 32, 'close': 55, 'low': 30, 'high': 60},
                              {'open': 58, 'close': 85, 'low': 55, 'high': 90}]},
    'five_waves': {'type': 'DRAW', 'signal': 'BUY', 'desc': '五浪上涨', 'data': [0, 60, 30, 80, 50, 100]},
    'w_bottom': {'type': 'DRAW', 'signal': 'BUY', 'desc': 'W底', 'data': [100, 0, 50, 0, 100]},
    'v_reversal': {'type': 'DRAW', 'signal': 'BUY', 'desc': 'V型反转', 'data': [100, 0, 100]},
    'dark_cloud': {'type': 'KLINE', 'signal': 'SELL', 'desc': '乌云盖顶',
                   'data': [{'open': 20, 'close': 80, 'low': 15, 'high': 85},
                            {'open': 90, 'close': 50, 'low': 45, 'high': 95}]},
    'three_crows': {'type': 'KLINE', 'signal': 'SELL', 'desc': '三只乌鸦',
                    'data': [{'open': 90, 'close': 70, 'low': 65, 'high': 95},
                             {'open': 68, 'close': 48, 'low': 45, 'high': 72},
                             {'open': 45, 'close': 25, 'low': 20, 'high': 48}]},
    'm_top': {'type': 'DRAW', 'signal': 'SELL', 'desc': 'M头', 'data': [0, 100, 50, 100, 0]},
    'head_shoulders': {'type': 'DRAW', 'signal': 'SELL', 'desc': '头肩顶', 'data': [0, 70, 40, 100, 40, 70, 0]},
}


# ... (normalize_series, calculate_indicators, analyze_kline_signals 保持不变) ...
def normalize_series(series):
    series = np.array(series)
    if np.std(series) == 0: return series
    return (series - np.mean(series)) / np.std(series)


def calculate_indicators(df):
    if 'close' not in df.columns: return df
    df['MA5'] = df['close'].rolling(5).mean()
    df['MA10'] = df['close'].rolling(10).mean()
    df['MA20'] = df['close'].rolling(20).mean()
    exp12 = df['close'].ewm(span=12, adjust=False).mean()
    exp26 = df['close'].ewm(span=26, adjust=False).mean()
    df['DIF'] = exp12 - exp26
    df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
    # 增加 KDJ, RSI 计算
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    low_list = df['low'].rolling(9, min_periods=9).min()
    high_list = df['high'].rolling(9, min_periods=9).max()
    rsv = (df['close'] - low_list) / (high_list - low_list) * 100
    df['K'] = rsv.ewm(com=2, adjust=False).mean()
    df['D'] = df['K'].ewm(com=2, adjust=False).mean()
    df['J'] = 3 * df['K'] - 2 * df['D']
    return df.fillna(0)


def analyze_kline_signals(df):
    signals = []
    if len(df) < 5: return signals
    for i in range(2, len(df)):
        curr = df.iloc[i];
        prev = df.iloc[i - 1]
        if prev['MA5'] < prev['MA10'] and curr['MA5'] > curr['MA10']: signals.append(
            {'idx': i, 'type': 'BUY', 'msg': 'MA金叉'})
        if prev['DIF'] < prev['DEA'] and curr['DIF'] > curr['DEA']: signals.append(
            {'idx': i, 'type': 'BUY', 'msg': 'MACD金叉'})
        if curr['K'] > curr['D'] and prev['K'] < prev['D'] and curr['K'] < 30: signals.append(
            {'idx': i, 'type': 'BUY', 'msg': 'KDJ金叉'})
    return signals


# ==========================================
# 3. 核心扫描 (启用阈值筛选)
# ==========================================
def run_analysis_core(target_pattern_data=None, filters=None):
    target_series = []
    has_pattern = False

    if target_pattern_data:
        if isinstance(target_pattern_data[0], (int, float)):
            target_series = target_pattern_data;
            has_pattern = True
        elif isinstance(target_pattern_data[0], dict):
            target_series = [x['close'] for x in target_pattern_data];
            has_pattern = True
    if has_pattern: norm_target = normalize_series(target_series)

    all_stocks = StockBasic.objects.all()
    results = []

    filters = filters or {}
    # 🔥 关键修复：接收并转换阈值参数，默认 60 分
    try:
        min_score = float(filters.get('minScore', 60))
    except:
        min_score = 60

    target_cap = filters.get('marketCap', '')

    try:
        min_c = float(filters.get('minClose') or 0); max_c = float(filters.get('maxClose') or 99999)
    except:
        min_c = 0; max_c = 99999

    for stock in all_stocks:
        m_cap = stock.market_cap or 0
        if target_cap == 'SMALL' and m_cap >= 50: continue
        if target_cap == 'LARGE' and m_cap <= 200: continue

        qs = StockDaily.objects.filter(ts_code=stock.ts_code).order_by('-trade_date')[:60]
        data = list(qs.values('trade_date', 'open_price', 'close_price', 'high_price', 'low_price'))
        if len(data) < 20: continue
        df = pd.DataFrame(data[::-1])
        df.rename(columns={'open_price': 'open', 'close_price': 'close', 'high_price': 'high', 'low_price': 'low'},
                  inplace=True)

        if not (min_c <= df.iloc[-1]['close'] <= max_c): continue

        # DTW 匹配
        dtw_score = 0
        match_data = []
        if has_pattern:
            if len(df) >= len(target_series):
                seg = df['close'].iloc[-len(target_series):].values
                dist, _ = fastdtw(norm_target, normalize_series(seg), dist=lambda x, y: abs(x - y))
                # 将距离转换为 0-100 的相似度分数
                dtw_score = max(0, 100 - dist * 2)
                match_data = seg.tolist()

        final_score = dtw_score if has_pattern else 60

        # 🔥 关键修复：真正使用阈值进行过滤
        if final_score < min_score: continue

        results.append({
            'code': stock.ts_code, 'name': stock.name, 'price': df.iloc[-1]['close'],
            'score': round(final_score, 1),
            'confidence': round(min(99, 50 + (final_score - 60) * 0.8), 1),
            'match_data': match_data,
            'match_type': 'BUY'
        })

    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:30]