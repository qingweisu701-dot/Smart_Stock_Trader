from django.db import models


class StockBasic(models.Model):
    ts_code = models.CharField(max_length=20, verbose_name='股票代码', primary_key=True)
    name = models.CharField(max_length=20, verbose_name='股票名称')
    industry = models.CharField(max_length=20, verbose_name='所属行业', null=True, blank=True)
    market_cap = models.FloatField(verbose_name='总市值(亿元)', null=True, blank=True)
    list_date = models.CharField(max_length=20, verbose_name='上市日期', null=True, blank=True)

    class Meta:
        verbose_name = '股票列表'

    def __str__(self):
        return f"{self.name} ({self.ts_code})"


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


class UserPattern(models.Model):
    PATTERN_TYPES = (('DRAW', '趋势手绘'), ('KLINE', 'K线构造'))

    name = models.CharField(max_length=50, verbose_name='形态名称')
    source_type = models.CharField(max_length=10, choices=PATTERN_TYPES, default='DRAW')
    description = models.CharField(max_length=200, blank=True, verbose_name='形态含义')
    # 存储核心数据：
    # 如果是 DRAW: "0.1,0.2,0.5..." (纯趋势序列)
    # 如果是 KLINE: JSON字符串，存储 [{"open":10, "close":12...}, {...}]
    data_points = models.TextField(verbose_name='数据序列')
    create_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-create_time']


class FavoriteStock(models.Model):
    GROUPS = (('DEFAULT', '默认分组'), ('WATCH', '观察仓'), ('TOP', '龙头股'))
    ts_code = models.CharField(max_length=20, verbose_name='股票代码')
    group = models.CharField(max_length=20, choices=GROUPS, default='DEFAULT', verbose_name='分组')
    add_time = models.DateTimeField(auto_now_add=True)
    notes = models.CharField(max_length=100, blank=True, verbose_name='备注')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['ts_code'], name='unique_fav_stock')]


class TradeRecord(models.Model):
    TRADE_TYPES = (('BUY', '买入'), ('SELL', '卖出'))
    ts_code = models.CharField(max_length=20)
    trade_date = models.DateField()
    trade_type = models.CharField(max_length=10, choices=TRADE_TYPES)
    price = models.FloatField()
    volume = models.IntegerField(default=100)
    strategy_name = models.CharField(max_length=50, default='手动交易')
    pnl = models.FloatField(null=True, blank=True)
    create_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-create_time']


class SystemMessage(models.Model):
    title = models.CharField(max_length=100)
    content = models.TextField()
    related_code = models.CharField(max_length=20, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    create_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-create_time']