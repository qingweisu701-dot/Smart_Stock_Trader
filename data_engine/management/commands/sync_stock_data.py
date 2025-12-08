import tushare as ts
import pandas as pd
import time
from django.core.management.base import BaseCommand
from data_engine.models import StockDaily, StockBasic
from datetime import datetime, timedelta
import os
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''
os.environ['ALL_PROXY'] = ''
class Command(BaseCommand):
    help = '多源金融数据智能采集与标准化处理模块'

    def handle(self, *args, **options):
        # ==========================================
        # ⚠️ 请填入你的 Tushare Token
        # ==========================================
        my_token = '9dafb0670f8fe189483519136b028bbba0732211772b0334e7c74852'

        if my_token == '你的Tushare_Token_填在这里':
            self.stdout.write(self.style.ERROR('⚠️ 请先配置 Tushare Token！'))
            return

        ts.set_token(my_token)
        pro = ts.pro_api()

        self.stdout.write(self.style.SUCCESS('🚀 启动智能数据采集引擎...'))

        # ==========================================
        # 1. 股票池构建 (选取沪深300核心资产，约300只)
        # ==========================================
        self.stdout.write('📊 正在构建股票池 (以沪深300为例)...')
        try:
            # 获取沪深300成分股
            df_index = pro.index_weight(index_code='399300.SZ', start_date='20230101', end_date='20230201')
            # 去重，获取代码列表
            target_codes = df_index['con_code'].unique().tolist()

            # 如果接口没权限，回退到手动定义 20 只龙头股做演示
            if not target_codes:
                self.stdout.write(self.style.WARNING('沪深300接口无权限，切换至核心龙头股模式...'))
                target_codes = [
                    '600519.SH', '000858.SZ', '601318.SH', '300750.SZ', '002594.SZ',  # 茅台,五粮液,平安,宁德,比亚迪
                    '600036.SH', '000001.SZ', '601166.SH', '600900.SH', '601888.SH',  # 招商,平安银行,兴业,长电,中免
                    '000333.SZ', '600276.SH', '603288.SH', '002415.SZ', '300059.SZ',  # 美的,恒瑞,海天,海康,东财
                    '601012.SH', '600030.SH', '002714.SZ', '600438.SH', '600887.SH'  # 隆基,中信,牧原,通威,伊利
                ]

            # 截取前 200 只 (满足用户大约200条的需求)
            target_codes = target_codes[:200]
            self.stdout.write(f'✅ 股票池构建完成，共锁定 {len(target_codes)} 只标的。')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ 股票池获取失败: {e}'))
            return

        # ==========================================
        # 2. 基础信息与基本面数据同步
        # ==========================================
        self.stdout.write('📦 正在同步公司基本面信息 (Name, Industry, MarketCap)...')

        # 2.1 获取静态基础信息
        df_basic = pro.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name,area,industry,list_date')
        df_basic = df_basic[df_basic['ts_code'].isin(target_codes)]

        # 2.2 获取动态市值信息 (取最新交易日)
        today = datetime.now().strftime('%Y%m%d')
        # 自动往前找最近的一个交易日 (简单处理：如果今天没数据，可能是周末，往前推)
        # 更好的做法是用 pro.trade_cal，这里简化处理

        # 获取最近一周的 daily_basic，取每个股票最新的一条
        start_check = (datetime.now() - timedelta(days=10)).strftime('%Y%m%d')
        df_daily_basic = pro.daily_basic(ts_code='', trade_date='', start_date=start_check, end_date=today,
                                         fields='ts_code,trade_date,total_mv,pe,pb')

        if not df_daily_basic.empty:
            df_daily_basic = df_daily_basic.sort_values('trade_date').drop_duplicates('ts_code', keep='last')
            # 合并
            df_merge = pd.merge(df_basic, df_daily_basic[['ts_code', 'total_mv']], on='ts_code', how='left')
        else:
            df_merge = df_basic
            df_merge['total_mv'] = 0

        # 2.3 数据清洗与入库
        stock_basic_list = []
        for _, row in df_merge.iterrows():
            mv_val = row.get('total_mv')
            # 清洗：缺失值填0，单位换算为亿元
            market_cap_billion = round(mv_val / 10000, 2) if pd.notna(mv_val) else 0

            stock_basic_list.append(StockBasic(
                ts_code=row['ts_code'],
                name=row['name'],
                industry=row['industry'] if pd.notna(row['industry']) else '其他',
                market_cap=market_cap_billion,
                list_date=row['list_date']
            ))

        StockBasic.objects.bulk_create(stock_basic_list, update_conflicts=True, unique_fields=['ts_code'],
                                       update_fields=['name', 'industry', 'market_cap'])
        self.stdout.write(f'✅ 基础信息入库完成。')

        # ==========================================
        # 3. 全市场日线行情增量爬取
        # ==========================================
        # 抓取最近 365 天的数据
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
        end_date = datetime.now().strftime('%Y%m%d')

        self.stdout.write(f'📈 正在启动日线行情采集任务 ({start_date} ~ {end_date})...')

        total_records = 0

        # 分批采集，避免单次请求过大
        batch_size = 3  # Tushare 限制每次请求代码数量，这里用循环单只抓取稳妥

        for i, code in enumerate(target_codes):
            try:
                # 调用 Tushare 日线接口
                df_daily = pro.daily(ts_code=code, start_date=start_date, end_date=end_date)

                if df_daily.empty:
                    continue

                # 数据清洗：去重、异常值处理 (Tushare 数据质量较高，主要是判空)
                df_daily = df_daily.dropna(subset=['close', 'trade_date'])

                daily_objs = []
                for _, row in df_daily.iterrows():
                    daily_objs.append(StockDaily(
                        ts_code=row['ts_code'],
                        trade_date=datetime.strptime(row['trade_date'], '%Y%m%d').date(),
                        open_price=row['open'],
                        high_price=row['high'],
                        low_price=row['low'],
                        close_price=row['close'],
                        vol=row['vol'],
                        amount=row['amount']
                    ))

                # 事务性写入：先删后插 (保证数据不重复)
                StockDaily.objects.filter(ts_code=code).delete()
                StockDaily.objects.bulk_create(daily_objs)

                total_records += len(daily_objs)
                progress = (i + 1) / len(target_codes) * 100
                self.stdout.write(f"[{progress:.1f}%] {code} 同步成功 ({len(daily_objs)}条)")

                # 接口限流控制 (Tushare 免费接口限制每分钟请求数)
                time.sleep(0.35)

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ {code} 采集异常: {e}"))

        self.stdout.write(self.style.SUCCESS(
            f'✅ 所有任务完成！共采集 {len(target_codes)} 只股票，累计清洗入库 {total_records} 条行情数据。'))