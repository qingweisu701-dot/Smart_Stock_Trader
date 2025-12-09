import numpy as np
import pandas as pd
import datetime
from .matcher import calculate_indicators


def run_lstm_prediction(code):
    """
    模拟 LSTM (长短期记忆网络) - 擅长捕捉长期趋势
    特点：曲线平滑，趋势性强
    """
    return _generate_mock_data(code, model_type="LSTM", volatility=0.02, trend_strength=0.1)


def run_ensemble_prediction(code):
    """
    模拟 Ensemble (集成学习/随机森林) - 擅长多因子分类
    特点：对突变敏感，曲线波动较大，不仅看趋势还看因子共振
    """
    return _generate_mock_data(code, model_type="Ensemble", volatility=0.04, trend_strength=0.05)


def _generate_mock_data(code, model_type, volatility, trend_strength):
    """
    通用模拟生成器
    """
    try:
        # 1. 历史数据
        dates = pd.date_range(end=datetime.date.today(), periods=90).strftime('%Y-%m-%d').tolist()
        base = 100 if not code.startswith('6') else 20
        prices = []
        curr = base
        for i in range(len(dates)):
            # 模拟波动
            noise = np.random.normal(0, volatility)
            trend = (i / 90) * trend_strength  # 趋势项
            curr = curr * (1 + trend + noise)
            prices.append(round(curr, 2))

        # 2. 未来预测 (5天)
        future_dates = pd.date_range(start=datetime.date.today() + datetime.timedelta(days=1), periods=5).strftime(
            '%Y-%m-%d').tolist()
        future_prices = []
        pred = prices[-1]

        # 不同的模型有不同的预测特征
        for i in range(5):
            if model_type == "LSTM":
                # LSTM: 惯性强，平滑
                change = np.random.normal(0.005, 0.01)
            else:
                # Ensemble: 波动大，可能出现反转
                change = np.random.normal(0, 0.03)

            pred = pred * (1 + change)
            future_prices.append(round(pred, 2))

        # 3. 因子分析 (复用)
        # 这里简单模拟，真实场景应调用 calculate_indicators 分析
        score = np.random.randint(40, 90)
        factors = [
            {'name': '趋势动量', 'type': 'bull', 'desc': f'{model_type} 模型捕捉到上涨动能'},
            {'name': '量价配合', 'type': 'bear' if score < 50 else 'bull',
             'desc': '成交量放大' if score > 60 else '缩量盘整'}
        ]

        # 4. 建议
        suggestion = 'HOLD'
        if score >= 70:
            suggestion = 'BUY'
        elif score <= 30:
            suggestion = 'SELL'

        return {
            'code': code,
            'model': model_type,
            'score': score,
            'suggestion': suggestion,
            'history_dates': dates,
            'history_prices': prices,
            'future_dates': future_dates,
            'future_prices': future_prices,
            'final_return': round((future_prices[-1] - prices[-1]) / prices[-1] * 100, 2),
            'factors': factors,
            'advice': {
                'buy_price': round(prices[-1] * 0.98, 2),
                'sell_price': round(prices[-1] * 1.05, 2),
                'period': '3-5天' if model_type == 'Ensemble' else '1-2周',
                'stop_loss': round(prices[-1] * 0.95, 2)
            }
        }
    except Exception as e:
        print(f"Pred Error: {e}")
        return None


# 统一入口
def run_predict_dispatch(code, model='LSTM'):
    if model == 'Ensemble':
        return run_ensemble_prediction(code)
    return run_lstm_prediction(code)