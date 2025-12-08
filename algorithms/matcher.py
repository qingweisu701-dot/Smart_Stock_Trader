import numpy as np
import pandas as pd
from fastdtw import fastdtw
from data_engine.models import StockDaily, StockBasic, UserPattern


# ==========================================
# 1. 基础工具
# ==========================================
def normalize_series(series):
    series = np.array(series)
    if np.std(series) == 0: return series
    return (series - np.mean(series)) / np.std(series)


def calculate_indicators(df):
    """计算 MACD, MA, RSI"""
    if 'close' not in df.columns: return df
    # MA
    df['MA5'] = df['close'].rolling(5).mean()
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


# ==========================================
# 2. 专业形态逻辑 (知识库应用)
# ==========================================
# 预设的标准走势 (归一化趋势)
PRESET_PATTERNS = {
    # 知识来源：[上涨趋势——这几个图形足够权威]
    'five_waves': {'data': [0, 6, 2, 8, 4, 10], 'desc': '五浪上涨(趋势加强)', 'type': 'BUY'},
    'w_bottom': {'data': [10, 0, 5, 0, 10], 'desc': 'W底(底部反转)', 'type': 'BUY'},
    'n_break': {'data': [0, 8, 4, 10], 'desc': 'N字突破(中继上涨)', 'type': 'BUY'},

    # 知识来源：[警惕！遇到这十种K线赶紧卖]
    'head_shoulders_top': {'data': [0, 8, 4, 10, 4, 8, 0], 'desc': '头肩顶(见顶卖出)', 'type': 'SELL'},
    'm_top': {'data': [0, 10, 5, 10, 0], 'desc': 'M头(双顶回落)', 'type': 'SELL'},
}


def check_kline_patterns(df):
    """检测单K线形态：乌云盖顶、长剑指天等"""
    signals = []
    if len(df) < 3: return signals

    curr = df.iloc[-1]
    prev = df.iloc[-2]

    # 1. 长剑指天 (射击之星) - 卖出信号
    # 定义：上影线长，实体小，处于高位
    body = abs(curr['close'] - curr['open'])
    upper = curr['high'] - max(curr['close'], curr['open'])
    if upper > 2 * body and body > 0:
        signals.append('长剑指天(风险)')

    # 2. 乌云盖顶 - 卖出信号
    # 定义：前阳后阴，阴线高开，收盘切入阳线实体一半以下
    if prev['close'] > prev['open'] and curr['close'] < curr['open']:
        mid_point = (prev['close'] + prev['open']) / 2
        if curr['open'] > prev['close'] and curr['close'] < mid_point:
            signals.append('乌云盖顶(见顶)')

    # 3. 均线多头排列 - 买入信号
    if curr['close'] > curr['MA5'] > curr['MA20']:
        signals.append('均线多头(趋势)')

    return signals


# ==========================================
# 3. 主分析与置信度计算
# ==========================================
def run_analysis_core(target_pattern_data=None, filters=None):
    """
    核心分析函数
    :param target_pattern_data: 目标形态数组 (若为None则只进行基本面筛选)
    :param filters: 筛选条件 {marketCap, sector, minScore...}
    """
    # 1. 准备数据
    has_pattern = target_pattern_data is not None and len(target_pattern_data) > 3
    if has_pattern:
        norm_target = normalize_series(target_pattern_data)

    all_stocks = StockBasic.objects.all()
    results = []

    min_score = float(filters.get('minScore', 60))
    target_cap = filters.get('marketCap', '')
    target_sector = filters.get('sector', '')

    for stock in all_stocks:
        # --- 基础筛选 (市值/行业) ---
        m_cap = stock.market_cap or 0
        # 市值筛选 (真实数据)
        if target_cap == 'SMALL' and m_cap >= 100: continue
        if target_cap == 'MID' and (m_cap < 100 or m_cap > 500): continue
        if target_cap == 'LARGE' and m_cap <= 500: continue

        # 行业筛选
        if target_sector and target_sector not in (stock.industry or ''): continue

        # --- 获取行情 (最近60天) ---
        qs = StockDaily.objects.filter(ts_code=stock.ts_code).order_by('-trade_date')[:60]
        data = list(qs.values('trade_date', 'open_price', 'close_price', 'high_price', 'low_price'))
        if len(data) < 20: continue

        # 转 DataFrame 并正序
        df = pd.DataFrame(data[::-1])
        df.rename(columns={'open_price': 'open', 'close_price': 'close', 'high_price': 'high', 'low_price': 'low'},
                  inplace=True)

        # --- 计算技术指标 & 形态 ---
        df = calculate_indicators(df)
        k_signals = check_kline_patterns(df)

        # --- DTW 匹配 ---
        dtw_score = 0
        match_data = []
        if has_pattern:
            # 滑动匹配：取最近的一段进行对比
            window = len(target_pattern_data)
            if len(df) >= window:
                segment = df['close'].iloc[-window:].values
                dist, _ = fastdtw(norm_target, normalize_series(segment), dist=lambda x, y: abs(x - y))
                dtw_score = max(0, 100 - dist * 2)  # 简单分数转换
                match_data = segment.tolist()

        # --- 综合置信度评分 ---
        # 基础分：如果有形态，以形态分为主；否则以技术面为主
        base_score = dtw_score if has_pattern else 60

        # 加分项：K线形态验证
        tech_bonus = 0
        if '均线多头' in str(k_signals): tech_bonus += 10
        if '长剑指天' in str(k_signals): tech_bonus -= 20  # 风险信号扣分

        final_score = base_score + tech_bonus
        if final_score < min_score: continue

        # 预测涨跌概率 (简单模拟)
        # 真实环境应用机器学习模型，这里用趋势强度模拟
        trend_strength = (df.iloc[-1]['close'] - df.iloc[-10]['close']) / df.iloc[-10]['close']
        win_rate = 50 + (trend_strength * 100) + (10 if final_score > 80 else 0)
        win_rate = min(95, max(5, win_rate))

        results.append({
            'code': stock.ts_code,
            'name': stock.name,
            'price': df.iloc[-1]['close'],
            'score': round(final_score, 1),
            'win_rate': round(win_rate, 1),  # 胜率预估
            'signals': k_signals,  # 触发的K线信号
            'match_data': match_data,
            'industry': stock.industry,
            'market_cap': stock.market_cap
        })

    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:30]