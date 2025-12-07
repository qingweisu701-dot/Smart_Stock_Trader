from django.db import models

class StockDaily(models.Model):
    """
    股票日线行情表
    """
    ts_code = models.CharField(max_length=20, verbose_name='股票代码', db_index=True)
    trade_date = models.DateField(verbose_name='交易日期', db_index=True)

    # 行情数据
    open_price = models.FloatField(verbose_name='开盘价')
    close_price = models.FloatField(verbose_name='收盘价')
    high_price = models.FloatField(verbose_name='最高价')
    low_price = models.FloatField(verbose_name='最低价')
    vol = models.FloatField(verbose_name='成交量(手)')
    amount = models.FloatField(verbose_name='成交额(千元)')

    class Meta:
        verbose_name = '日线行情'
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=['ts_code', 'trade_date']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['ts_code', 'trade_date'], name='unique_stock_date')
        ]

    def __str__(self):
        return f"{self.ts_code} - {self.trade_date}"


# =========================================================
# 新增的交易记录表
# =========================================================
class TradeRecord(models.Model):
    """
    交易记录表
    """
    TRADE_TYPES = (
        ('BUY', '买入'),
        ('SELL', '卖出'),
    )

    ts_code = models.CharField(max_length=20, verbose_name='股票代码')
    trade_date = models.DateField(verbose_name='交易日期')
    trade_type = models.CharField(max_length=10, choices=TRADE_TYPES, verbose_name='交易方向')
    price = models.FloatField(verbose_name='成交均价')
    volume = models.IntegerField(verbose_name='成交手数')
    strategy_name = models.CharField(max_length=50, verbose_name='触发策略', default='DTW形态匹配')

    create_time = models.DateTimeField(auto_now_add=True, verbose_name='记录时间')

    class Meta:
        verbose_name = '模拟交易记录'
        verbose_name_plural = verbose_name
        ordering = ['-create_time']

    def __str__(self):
        return f"{self.ts_code} {self.trade_type} @ {self.price}"