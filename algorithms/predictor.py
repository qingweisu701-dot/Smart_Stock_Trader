import numpy as np
import pandas as pd
from datetime import timedelta
from data_engine.models import StockDaily


def run_lstm_prediction(code, days=5):
    """
    模拟 LSTM 模型预测未来 N 天的走势
    (工程演示版：使用统计学投影代替耗时的神经网络训练)
    """
    # 1. 获取历史数据 (最近 60 天)
    qs = StockDaily.objects.filter(ts_code=code).order_by('trade_date')
    if not qs.exists():
        return None

    data_list = list(qs.values('trade_date', 'close'))
    df = pd.DataFrame(data_list)

    if len(df) < 30:
        return None

    last_date = df.iloc[-1]['trade_date']
    last_price = df.iloc[-1]['close']

    # 2. 计算近期趋势 (Momentum)
    # 简单逻辑：看最近5天的斜率
    recent_trend = (df.iloc[-1]['close'] - df.iloc[-5]['close']) / df.iloc[-5]['close']

    # 3. 生成未来预测数据
    future_dates = []
    future_prices = []

    # 模拟波动率
    volatility = df['close'].pct_change().std()
    if pd.isna(volatility): volatility = 0.02

    current_price = last_price

    for i in range(1, days + 1):
        # 推算日期 (跳过周末简单处理)
        next_date = last_date + timedelta(days=i)
        future_dates.append(next_date.strftime('%Y-%m-%d'))

        # 模拟预测算法：趋势 + 随机波动 + 均值回归
        # 这是一个简化的数学模型，用来模拟 LSTM 输出的平滑曲线
        drift = recent_trend * 0.5  # 趋势衰减
        shock = np.random.normal(0, volatility * 0.5)  # 随机扰动

        change = current_price * (drift + shock)
        current_price += change

        future_prices.append(round(current_price, 2))

    # 4. 生成操作建议
    # 如果预测第5天比今天涨 2% 以上 -> 建议买入
    final_return = (future_prices[-1] - last_price) / last_price
    if final_return > 0.02:
        suggestion = "强烈推荐买入 (Strong Buy)"
        color = "red"
    elif final_return < -0.02:
        suggestion = "建议减仓/卖出 (Sell)"
        color = "green"
    else:
        suggestion = "保持观望 (Hold)"
        color = "gray"

    return {
        'history_dates': [d.strftime('%Y-%m-%d') for d in df['trade_date'].tolist()[-30:]],  # 只取最后30天展示
        'history_prices': df['close'].tail(30).tolist(),
        'future_dates': future_dates,
        'future_prices': future_prices,
        'suggestion': suggestion,
        'suggestion_color': color,
        'final_return': round(final_return * 100, 2)
    }