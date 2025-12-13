import numpy as np
import pandas as pd
from fastdtw import fastdtw
from data_engine.models import StockDaily, StockBasic

# ==========================================
# 1. 形态库 (确保这里有数据)
# ==========================================
PRESET_PATTERNS = {
    # =========== 📈 看涨形态 (Bullish) ===========
    'hammer_low': {'type': 'KLINE', 'signal': 'BUY', 'desc': '低位倒锤线',
                   'data': [{'open': 20, 'close': 25, 'low': 5, 'high': 26}]},
    'morning_star': {'type': 'KLINE', 'signal': 'BUY', 'desc': '启明之星',
                     'data': [{'open': 80, 'close': 20, 'low': 15, 'high': 85},
                              {'open': 10, 'close': 15, 'low': 5, 'high': 20},
                              {'open': 25, 'close': 70, 'low': 20, 'high': 75}]},
    'red_soldiers': {'type': 'KLINE', 'signal': 'BUY', 'desc': '红三兵',
                     'data': [{'open': 10, 'close': 30, 'low': 5, 'high': 35},
                              {'open': 32, 'close': 55, 'low': 30, 'high': 60},
                              {'open': 58, 'close': 85, 'low': 55, 'high': 90}]},
    'bull_engulfing': {'type': 'KLINE', 'signal': 'BUY', 'desc': '旭日东升',
                       'data': [{'open': 50, 'close': 40, 'low': 38, 'high': 52},
                                {'open': 35, 'close': 60, 'low': 35, 'high': 62}]},
    'piercing': {'type': 'KLINE', 'signal': 'BUY', 'desc': '曙光初现',
                 'data': [{'open': 60, 'close': 30, 'low': 28, 'high': 62},
                          {'open': 20, 'close': 50, 'low': 18, 'high': 52}]},
    'five_waves': {'type': 'DRAW', 'signal': 'BUY', 'desc': '五浪上涨', 'data': [0, 60, 30, 80, 50, 100]},
    'w_bottom': {'type': 'DRAW', 'signal': 'BUY', 'desc': 'W底', 'data': [100, 0, 50, 0, 100]},
    'v_reversal': {'type': 'DRAW', 'signal': 'BUY', 'desc': 'V型反转', 'data': [100, 0, 100]},
    'round_bottom': {'type': 'DRAW', 'signal': 'BUY', 'desc': '圆弧底', 'data': [100, 80, 60, 50, 45, 50, 60, 80, 100]},
    'cup_handle': {'type': 'DRAW', 'signal': 'BUY', 'desc': '杯柄形态', 'data': [100, 50, 40, 40, 50, 90, 80, 85, 120]},
    'asc_triangle': {'type': 'DRAW', 'signal': 'BUY', 'desc': '上升三角形',
                     'data': [50, 100, 60, 100, 70, 100, 80, 120]},

    # =========== 📉 看跌形态 (Bearish) ===========
    'dark_cloud': {'type': 'KLINE', 'signal': 'SELL', 'desc': '乌云盖顶',
                   'data': [{'open': 20, 'close': 80, 'low': 15, 'high': 85},
                            {'open': 90, 'close': 50, 'low': 45, 'high': 95}]},
    'three_crows': {'type': 'KLINE', 'signal': 'SELL', 'desc': '三只乌鸦',
                    'data': [{'open': 90, 'close': 70, 'low': 65, 'high': 95},
                             {'open': 68, 'close': 48, 'low': 45, 'high': 72},
                             {'open': 45, 'close': 25, 'low': 20, 'high': 48}]},
    'evening_star': {'type': 'KLINE', 'signal': 'SELL', 'desc': '黄昏之星',
                     'data': [{'open': 20, 'close': 70, 'low': 15, 'high': 75},
                              {'open': 75, 'close': 80, 'low': 70, 'high': 85},
                              {'open': 75, 'close': 25, 'low': 20, 'high': 78}]},
    'bear_engulfing': {'type': 'KLINE', 'signal': 'SELL', 'desc': '穿头破脚',
                       'data': [{'open': 30, 'close': 40, 'low': 28, 'high': 42},
                                {'open': 45, 'close': 25, 'low': 22, 'high': 48}]},
    'shooting_star': {'type': 'KLINE', 'signal': 'SELL', 'desc': '射击之星',
                      'data': [{'open': 30, 'close': 28, 'low': 25, 'high': 60}]},
    'hanging_man': {'type': 'KLINE', 'signal': 'SELL', 'desc': '吊颈线',
                    'data': [{'open': 80, 'close': 78, 'low': 40, 'high': 82}]},
    'm_top': {'type': 'DRAW', 'signal': 'SELL', 'desc': 'M头', 'data': [0, 100, 50, 100, 0]},
    'head_shoulders': {'type': 'DRAW', 'signal': 'SELL', 'desc': '头肩顶', 'data': [0, 70, 40, 100, 40, 70, 0]},
    'round_top': {'type': 'DRAW', 'signal': 'SELL', 'desc': '圆弧顶', 'data': [20, 50, 80, 90, 100, 90, 80, 50, 20]},
    'inv_v_top': {'type': 'DRAW', 'signal': 'SELL', 'desc': '倒V顶', 'data': [0, 50, 100, 50, 0]},
    'desc_triangle': {'type': 'DRAW', 'signal': 'SELL', 'desc': '下降三角形',
                      'data': [100, 50, 90, 50, 80, 50, 70, 20]},
}


def normalize_series(series):
    series = np.array(series)
    if np.std(series) == 0: return series
    return (series - np.mean(series)) / np.std(series)


def calculate_indicators(df):
    for col in ['close', 'open', 'high', 'low']:
        if col not in df.columns: return df

    # 填充默认值
    for col in ['MA5', 'MA10', 'MA20', 'K', 'D', 'J', 'RSI', 'MACD', 'DIF', 'DEA']:
        if col not in df.columns: df[col] = 0.0

    if len(df) < 2: return df

    df['MA5'] = df['close'].rolling(5).mean().fillna(0)
    df['MA10'] = df['close'].rolling(10).mean().fillna(0)
    df['MA20'] = df['close'].rolling(20).mean().fillna(0)

    exp12 = df['close'].ewm(span=12, adjust=False).mean()
    exp26 = df['close'].ewm(span=26, adjust=False).mean()
    df['DIF'] = exp12 - exp26
    df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
    df['MACD'] = (df['DIF'] - df['DEA']) * 2

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
        curr = df.iloc[i]
        prev = df.iloc[i - 1]
        if prev['MA5'] < prev['MA10'] and curr['MA5'] > curr['MA10']:
            signals.append({'idx': i, 'type': 'BUY', 'msg': 'MA金叉'})
        if prev['DIF'] < prev['DEA'] and curr['DIF'] > curr['DEA']:
            signals.append({'idx': i, 'type': 'BUY', 'msg': 'MACD金叉'})
    return signals


def check_logic_conditions(df, logic_list):
    """
    Evaluate advanced logic conditions.
    logic_list: [{ 'logic': 'AND', 'field': 'MACD', 'op': 'gt', 'val': 0 }, ...]
    """
    if not logic_list: return True
    
    # 获取最新一行数据 (latest)
    curr = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else curr
    
    result = True
    
    for idx, item in enumerate(logic_list):
        # 1. 获取左值 (Indicator Value)
        field = item.get('field')
        if not field: continue
        
        val_left = 0
        if field in curr: val_left = curr[field]
        elif field == 'close': val_left = curr['close']
        
        # 2. 获取右值 (Target Value)
        val_right = float(item.get('val', 0))
        
        # 3. 计算单项结果
        op = item.get('op')
        term_res = False
        
        if op == 'gt': term_res = val_left > val_right
        elif op == 'lt': term_res = val_left < val_right
        elif op == 'gte': term_res = val_left >= val_right
        elif op == 'lte': term_res = val_left <= val_right
        elif op == 'eq': term_res = abs(val_left - val_right) < 0.01
        elif op == 'cross_up': # 上穿：昨<阀 AND 今>阀
             val_prev = prev[field] if field in prev else 0
             term_res = val_prev < val_right and val_left > val_right
        elif op == 'cross_down':
             val_prev = prev[field] if field in prev else 0
             term_res = val_prev > val_right and val_left < val_right

        # 4. 逻辑组合 (AND / OR)
        logic = item.get('logic', 'AND')
        if idx == 0:
            result = term_res
        else:
            if logic == 'AND': result = result and term_res
            elif logic == 'OR': result = result or term_res
            
    return result


def run_analysis_core(target_pattern_data=None, filters=None, pattern_name=None):
    target_series = []
    has_pattern = False

    if target_pattern_data:
        if isinstance(target_pattern_data[0], (int, float)):
            target_series = target_pattern_data;
            has_pattern = True
        elif isinstance(target_pattern_data[0], dict):
            target_series = [x['close'] for x in target_pattern_data];
            has_pattern = True

    if has_pattern:
        norm_target = normalize_series(target_series)

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
        if filters.get('marketCap') == 'LARGE' and m_cap <= 200: continue

        qs = StockDaily.objects.filter(ts_code=stock.ts_code).order_by('-trade_date')[:60]
        data = list(qs.values('trade_date', 'open_price', 'close_price', 'high_price', 'low_price'))
        if len(data) < 20: continue

        df = pd.DataFrame(data[::-1])
        df.rename(columns={'open_price': 'open', 'close_price': 'close', 'high_price': 'high', 'low_price': 'low'},
                  inplace=True)
        curr = df.iloc[-1]

        dtw_score = 0
        match_data = []
        if has_pattern:
            window = len(target_series)
            if len(df) >= window:
                seg = df['close'].iloc[-window:].values
                dist, _ = fastdtw(norm_target, normalize_series(seg), dist=lambda x, y: abs(x - y))
                dtw_score = max(0, 100 - dist * 2)
                match_data = seg.tolist()

        final = dtw_score if has_pattern else 60
        final = dtw_score if has_pattern else 60
        if final < min_score: continue

        # 🔥 新增：检查高级组合逻辑
        if filters.get('logicConditions'):
            if not check_logic_conditions(df, filters['logicConditions']):
                continue

        results.append({
            'code': stock.ts_code, 'name': stock.name, 'price': round(curr['close'], 2),
            'score': round(final, 1), 'confidence': 85, 'match_data': match_data, 'match_type': 'BUY',
            'reason': pattern_name if has_pattern else '技术指标优选'
        })

    results.sort(key=lambda x: x['score'], reverse=True)
    # 📉 兜底机制：如果数据库没数据，生成模拟数据演示 (Demo Mode)
    results.sort(key=lambda x: x['score'], reverse=True)
    # 📉 已移除：不再生成虚拟演示数据，真实反映市场情况
            
    return results[:30]