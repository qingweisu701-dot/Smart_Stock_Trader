from django.db import models


# 1. 股票基础信息 (用于市值筛选、行业分类)
class StockBasic(models.Model):
    ts_code = models.CharField(max_length=20, verbose_name='股票代码', primary_key=True)
    name = models.CharField(max_length=20, verbose_name='股票名称')
    industry = models.CharField(max_length=20, verbose_name='所属行业', null=True, blank=True)
    market_cap = models.FloatField(verbose_name='总市值(亿元)', null=True, blank=True)
    list_date = models.CharField(max_length=20, verbose_name='上市日期', null=True, blank=True)

    class Meta:
        verbose_name = '股票列表'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.name} ({self.ts_code})"


# 2. 日线行情 (核心数据)
class StockDaily(models.Model):
    ts_code = models.CharField(max_length=20, verbose_name='股票代码', db_index=True)
    trade_date = models.DateField(verbose_name='交易日期', db_index=True)
    open_price = models.FloatField(verbose_name='开盘价')
    close_price = models.FloatField(verbose_name='收盘价')
    high_price = models.FloatField(verbose_name='最高价')
    low_price = models.FloatField(verbose_name='最低价')
    vol = models.FloatField(verbose_name='成交量(手)')
    amount = models.FloatField(verbose_name='成交额(千元)')

    class Meta:
        verbose_name = '日线行情'
        indexes = [models.Index(fields=['ts_code', 'trade_date'])]
        constraints = [models.UniqueConstraint(fields=['ts_code', 'trade_date'], name='unique_stock_date')]

    def __str__(self):
        return f"{self.ts_code} - {self.trade_date}"


# 3. [新增] 图形形态库 (预设+用户手绘)
class UserPattern(models.Model):
    PATTERN_TYPES = (('PRESET', '系统预设'), ('CUSTOM', '用户自定义'))

    name = models.CharField(max_length=50, verbose_name='形态名称')
    type = models.CharField(max_length=10, choices=PATTERN_TYPES, default='CUSTOM')
    description = models.CharField(max_length=200, blank=True, verbose_name='形态含义(买入/卖出)')
    # 存储归一化后的Y轴数据点，逗号分隔，如 "0.1,0.5,0.8,0.2"
    data_points = models.TextField(verbose_name='数据点序列')
    create_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '形态管理'
        ordering = ['-create_time']

    def get_data_list(self):
        return [float(x) for x in self.data_points.split(',')]


# 4. [新增] 自选股收藏
class FavoriteStock(models.Model):
    ts_code = models.CharField(max_length=20, verbose_name='股票代码')
    add_time = models.DateTimeField(auto_now_add=True)
    notes = models.CharField(max_length=100, blank=True, verbose_name='备注')

    class Meta:
        verbose_name = '自选股'
        constraints = [models.UniqueConstraint(fields=['ts_code'], name='unique_fav_stock')]


# 5. 交易记录 (升级：支持卖出)
class TradeRecord(models.Model):
    TRADE_TYPES = (('BUY', '买入'), ('SELL', '卖出'))

    ts_code = models.CharField(max_length=20, verbose_name='股票代码')
    trade_date = models.DateField(verbose_name='交易日期')
    trade_type = models.CharField(max_length=10, choices=TRADE_TYPES, verbose_name='交易方向')
    price = models.FloatField(verbose_name='成交单价')
    volume = models.IntegerField(default=100, verbose_name='成交数量(股)')
    strategy_name = models.CharField(max_length=50, verbose_name='策略来源', default='手动交易')

    # 卖出时计算盈亏
    pnl = models.FloatField(null=True, blank=True, verbose_name='盈亏金额')
    create_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '交易记录'
        ordering = ['-create_time']