import numpy as np
import pandas as pd
from fastdtw import fastdtw
from data_engine.models import StockDaily, StockBasic

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


def normalize_series(series):
    series = np.array(series)
    if np.std(series) == 0: return series
    return (series - np.mean(series)) / np.std(series)


def calculate_indicators(df):
    # 必需列检查
    for col in ['close', 'open', 'high', 'low']:
        if col not in df.columns: return df

    # 初始化目标列
    target_cols = ['MA5','MA10','MA20','K','D','J','RSI','MACD','DIF','DEA']
    for col in target_cols:
        if col not in df.columns: df[col] = 0.0

    if len(df) < 2: return df

    # MA
    df['MA5'] = df['close'].rolling(5).mean()
    df['MA10'] = df['close'].rolling(10).mean()
    df['MA20'] = df['close'].rolling(20).mean()

    # MACD
    exp12 = df['close'].ewm(span=12, adjust=False).mean()
    exp26 = df['close'].ewm(span=26, adjust=False).mean()
    df['DIF'] = exp12 - exp26
    df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
    df['MACD'] = (df['DIF'] - df['DEA']) * 2

    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # KDJ
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
    return signals


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

    try:
        min_score = float(filters.get('minScore', 60))
    except:
        min_score = 60

    for stock in all_stocks:
        m_cap = stock.market_cap or 0
        if filters.get('marketCap') == 'SMALL' and m_cap >= 50: continue

        qs = StockDaily.objects.filter(ts_code=stock.ts_code).order_by('-trade_date')[:60]
        data = list(qs.values('trade_date', 'open_price', 'close_price', 'high_price', 'low_price'))
        if len(data) < 20: continue

        df = pd.DataFrame(data[::-1])
        df.rename(columns={'open_price': 'open', 'close_price': 'close', 'high_price': 'high', 'low_price': 'low'},
                  inplace=True)

        dtw_score = 0
        if has_pattern:
            window = len(target_series)
            if len(df) >= window:
                seg = df['close'].iloc[-window:].values
                dist, _ = fastdtw(norm_target, normalize_series(seg), dist=lambda x, y: abs(x - y))
                dtw_score = max(0, 100 - dist * 2)

        final = dtw_score if has_pattern else 60
        if final < min_score: continue

        results.append({
            'code': stock.ts_code, 'name': stock.name, 'price': round(df.iloc[-1]['close'], 2),
            'score': round(final, 1), 'confidence': 85, 'match_data': [], 'match_type': 'BUY'
        })

    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:30]