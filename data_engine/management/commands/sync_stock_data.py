import pandas as pd
import numpy as np
from django.core.management.base import BaseCommand
from data_engine.models import StockDaily
from datetime import datetime, timedelta
import random


class Command(BaseCommand):
    help = '生成仿真测试数据 (用于网络不通时的开发调试)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('检测到网络连接不稳定，切换为【生成仿真数据模式】...'))

        # 定义我们要生成的 3 只股票
        target_stocks = [
            {'code': '000001', 'name': '平安仿真', 'start_price': 10.0},
            {'code': '600519', 'name': '茅台仿真', 'start_price': 1500.0},
            {'code': '300750', 'name': '宁德仿真', 'start_price': 200.0},
        ]

        # 生成最近 1 年的数据
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=365)
        date_range = pd.date_range(start=start_date, end=end_date, freq='B')  # 'B' 代表仅工作日

        for stock in target_stocks:
            code = stock['code']
            name = stock['name']
            price = stock['start_price']

            self.stdout.write(f'正在生成 {code} - {name} 的数据...', ending='')

            data_list = []

            for single_date in date_range:
                # 模拟随机涨跌幅 (-3% 到 +3%)
                change_pct = random.uniform(-0.03, 0.03)

                # 计算当天的 OHLC (开高低收)
                curr_open = price * (1 + random.uniform(-0.01, 0.01))
                curr_close = price * (1 + change_pct)
                curr_high = max(curr_open, curr_close) * (1 + random.uniform(0, 0.01))
                curr_low = min(curr_open, curr_close) * (1 - random.uniform(0, 0.01))

                # 模拟成交量
                vol = random.randint(10000, 100000)
                amount = vol * curr_close

                # 更新第二天的基准价
                price = curr_close

                # 存入列表
                # =========================================================
                # 🔥【修复】使用新的字段名 open_price, close_price ...
                # =========================================================
                data_list.append(StockDaily(
                    ts_code=code,
                    trade_date=single_date.date(),
                    open_price=round(curr_open, 2),   # 修正
                    high_price=round(curr_high, 2),   # 修正
                    low_price=round(curr_low, 2),     # 修正
                    close_price=round(curr_close, 2), # 修正
                    vol=vol,
                    amount=amount
                ))

            # 批量插入数据库
            StockDaily.objects.filter(ts_code=code).delete()
            StockDaily.objects.bulk_create(data_list)

            self.stdout.write(self.style.SUCCESS(f' -> 成功生成 {len(data_list)} 条记录'))

        self.stdout.write(self.style.SUCCESS('所有仿真数据生成完毕！您可以开始开发前端了。'))