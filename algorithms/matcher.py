import numpy as np
import pandas as pd
from fastdtw import fastdtw
from data_engine.models import StockDaily, StockBasic


# ==========================================
# 1. 基础工具函数
# ==========================================

def normalize_series(series):
    """
    归一化序列 (Z-Score标准化)
    用于将不同价格区间的股票（如茅台和农行）放在同一尺度下比较形态
    """
    series = np.array(series)
    if np.std(series) == 0:
        return series
    return (series - np.mean(series)) / np.std(series)


def calculate_indicators(df):
    """
    计算技术指标: MA, MACD, RSI
    """
    # 确保有 close 列
    if 'close' not in df.columns:
        return df

    # 1. 均线 (MA)
    df['MA5'] = df['close'].rolling(window=5).mean()
    df['MA10'] = df['close'].rolling(window=10).mean()
    df['MA20'] = df['close'].rolling(window=20).mean()

    # 2. MACD (12, 26, 9)
    exp12 = df['close'].ewm(span=12, adjust=False).mean()
    exp26 = df['close'].ewm(span=26, adjust=False).mean()
    df['DIF'] = exp12 - exp26
    df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
    # MACD 柱状图
    df['MACD_Bar'] = (df['DIF'] - df['DEA']) * 2

    # 3. RSI (14)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    return df.fillna(0)


def check_kline_patterns(df):
    """
    单K线/组合形态识别
    返回识别到的形态名称列表 (如: ['乌云盖顶', '均线多头'])
    """
    signals = []
    if len(df) < 3:
        return signals

    curr = df.iloc[-1]  # 当天
    prev = df.iloc[-2]  # 昨天

    # --- 1. 风险形态识别 (卖出信号) ---

    # [长剑指天 / 射击之星]
    # 定义：上影线长度 > 2倍实体长度，且实体较小，通常在高位
    body_len = abs(curr['close'] - curr['open'])
    upper_shadow = curr['high'] - max(curr['close'], curr['open'])
    lower_shadow = min(curr['close'], curr['open']) - curr['low']

    # 简单的判定逻辑
    if upper_shadow > 2 * body_len and body_len > 0 and upper_shadow > 2 * lower_shadow:
        signals.append('长剑指天(风险)')

    # [乌云盖顶]
    # 定义：前一根长阳，今日高开低走大阴线，收盘价切入前一日实体的一半以下
    if prev['close'] > prev['open']:  # 昨天阳线
        mid_point = (prev['open'] + prev['close']) / 2
        # 今天阴线，开盘高于昨天收盘，收盘低于昨天中点
        if curr['close'] < curr['open'] and curr['open'] > prev['close'] and curr['close'] < mid_point:
            signals.append('乌云盖顶(见顶)')

    # [断头铡刀]
    # 定义：一根大阴线跌破 MA5, MA10, MA20 三条均线
    if curr['close'] < curr['open']:  # 阴线
        if curr['open'] > max(curr['MA5'], curr['MA10'], curr['MA20']) and \
                curr['close'] < min(curr['MA5'], curr['MA10'], curr['MA20']):
            signals.append('断头铡刀(大跌)')

    # --- 2. 机会形态识别 (买入信号) ---

    # [均线多头排列]
    if curr['close'] > curr['MA5'] > curr['MA10'] > curr['MA20']:
        signals.append('均线多头')

    # [MACD 金叉]
    if prev['DIF'] < prev['DEA'] and curr['DIF'] > curr['DEA']:
        signals.append('MACD金叉')

    return signals


# ==========================================
# 2. 核心分析函数
# ==========================================

def run_analysis_core(target_pattern_data=None, filters=None):
    """
    核心全市场扫描与匹配函数

    参数:
    - target_pattern_data: list (归一化前的价格序列，如 [10, 12, 11, 15...])
                           如果为 None，则只进行基础筛选，不进行 DTW 形态匹配。
    - filters: dict (筛选条件，如 {'minScore': 80, 'marketCap': 'LARGE', ...})

    返回:
    - results: list (匹配结果列表)
    """
    # 1. 准备形态数据
    has_pattern = target_pattern_data is not None and len(target_pattern_data) > 3
    norm_target = []

    if has_pattern:
        # 对用户输入/预设的形态进行归一化，以便与股票走势比较
        norm_target = normalize_series(target_pattern_data)

    # 2. 获取所有股票基础信息 (用于市值/行业筛选)
    all_stocks = StockBasic.objects.all()
    results = []

    # 解析筛选参数
    filters = filters or {}
    min_score = float(filters.get('minScore', 60))
    target_cap = filters.get('marketCap', '')  # 'LARGE', 'MID', 'SMALL' 或 ''
    target_sector = filters.get('sector', '')

    # 3. 遍历全市场股票
    for stock in all_stocks:
        # --- A. 基础条件筛选 (加速循环) ---

        # 1. 市值筛选 (StockBasic 中的 market_cap 单位为亿元)
        m_cap = stock.market_cap or 0
        if target_cap == 'SMALL' and m_cap >= 100: continue
        if target_cap == 'MID' and (m_cap < 100 or m_cap > 500): continue
        if target_cap == 'LARGE' and m_cap <= 500: continue

        # 2. 行业筛选 (模糊匹配)
        if target_sector and target_sector not in (stock.industry or ''):
            continue

        # --- B. 获取行情数据 ---
        # 优化：只取最近 60 个交易日的数据进行匹配，太久的数据无意义且慢
        qs = StockDaily.objects.filter(ts_code=stock.ts_code).order_by('-trade_date')[:60]
        data = list(qs.values('trade_date', 'open_price', 'close_price', 'high_price', 'low_price', 'vol'))

        # 数据过少则跳过 (刚上市的新股)
        if len(data) < 20:
            continue

        # 数据库取出是倒序的(最新在前)，转 DataFrame 时要反转为正序(时间轴从左到右)
        df = pd.DataFrame(data[::-1])
        # 重命名列以符合习惯
        df.rename(columns={'open_price': 'open', 'close_price': 'close', 'high_price': 'high', 'low_price': 'low'},
                  inplace=True)

        # --- C. 计算技术指标 & 形态 ---
        df = calculate_indicators(df)

        # 获取最新的 K 线形态信号
        k_signals = check_kline_patterns(df)

        # --- D. DTW 形态匹配 (如果有目标形态) ---
        dtw_score = 0
        match_data = []

        if has_pattern:
            # 滑动窗口匹配：取股票最近的一段(长度与目标形态一致)来进行比对
            window_len = len(target_pattern_data)
            if len(df) >= window_len:
                # 取出最近 window_len 天的收盘价
                segment = df['close'].iloc[-window_len:].values
                # 归一化后计算欧氏距离 (FastDTW)
                dist, _ = fastdtw(norm_target, normalize_series(segment), dist=lambda x, y: abs(x - y))
                # 将距离转换为分数 (距离越小分数越高)
                # 这里的公式可以根据需要调整，例如：Score = 100 / (1 + distance)
                dtw_score = max(0, 100 - dist * 2)
                match_data = segment.tolist()
            else:
                # 股票数据不够长，无法匹配
                dtw_score = 0

        # --- E. 综合评分 & 置信度评估 ---

        # 基础分
        if has_pattern:
            final_score = dtw_score
        else:
            # 如果没选形态，只看基本面，给一个及格分让它能显示出来
            final_score = 60

        # K线信号加分项
        tech_bonus = 0
        if '均线多头' in k_signals: tech_bonus += 10
        if 'MACD金叉' in k_signals: tech_bonus += 5
        if '长剑指天(风险)' in str(k_signals): tech_bonus -= 20  # 风险扣分
        if '乌云盖顶(见顶)' in str(k_signals): tech_bonus -= 20  # 风险扣分

        final_score += tech_bonus

        # 阈值过滤
        if final_score < min_score:
            continue

        # 预测胜率/置信度 (模拟逻辑，真实项目可接入 LSTM 预测值)
        # 逻辑：基础50% + 分数加成 + 趋势加成
        trend_strength = 0
        if df.iloc[-1]['close'] > df.iloc[-1]['MA20']: trend_strength = 10

        confidence = 50 + (final_score - 60) * 0.5 + trend_strength
        confidence = min(99, max(10, confidence))  # 限制在 10-99 之间

        # --- F. 打包结果 ---
        results.append({
            'code': stock.ts_code,
            'name': stock.name,
            'price': round(df.iloc[-1]['close'], 2),
            'score': round(final_score, 1),
            'confidence': round(confidence, 1),  # AI 置信度
            'signals': k_signals,  # 触发的K线形态列表
            'match_data': match_data,  # 匹配到的走势片段(用于前端绘图)
            'industry': stock.industry,
            'market_cap': stock.market_cap,
            # 简单的买卖建议标签
            'match_type': 'SELL' if tech_bonus < 0 else 'BUY'
        })

    # 4. 排序与返回
    # 按分数从高到低排序，取前 30 个
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:30]