from django.db import models

class StockBasic(models.Model):
    ts_code = models.CharField(max_length=20, verbose_name='股票代码', primary_key=True)
    name = models.CharField(max_length=20, verbose_name='股票名称')
    industry = models.CharField(max_length=20, verbose_name='所属行业', null=True, blank=True)
    market_cap = models.FloatField(verbose_name='总市值(亿元)', null=True, blank=True)
    list_date = models.CharField(max_length=20, verbose_name='上市日期', null=True, blank=True)
    is_dragon_tiger = models.BooleanField(default=False, verbose_name='是否龙虎榜')
    class Meta: verbose_name = '股票列表'

class StockDaily(models.Model):
    ts_code = models.CharField(max_length=20, db_index=True)
    trade_date = models.DateField(db_index=True)
    open_price = models.FloatField()
    close_price = models.FloatField()
    high_price = models.FloatField()
    low_price = models.FloatField()
    vol = models.FloatField()
    amount = models.FloatField()
    class Meta:
        indexes = [models.Index(fields=['ts_code', 'trade_date'])]
        constraints = [models.UniqueConstraint(fields=['ts_code', 'trade_date'], name='unique_stock_date')]

class UserPattern(models.Model):
    PATTERN_TYPES = (('DRAW', '趋势手绘'), ('KLINE', 'K线构造'))
    name = models.CharField(max_length=50)
    source_type = models.CharField(max_length=10, choices=PATTERN_TYPES, default='DRAW')
    description = models.CharField(max_length=200, blank=True)
    data_points = models.TextField()
    create_time = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ['-create_time']

class PatternFavorite(models.Model):
    pattern_id = models.CharField(max_length=50)
    pattern_type = models.CharField(max_length=20, default='PRESET')
    add_time = models.DateTimeField(auto_now_add=True)
    class Meta: constraints = [models.UniqueConstraint(fields=['pattern_id', 'pattern_type'], name='unique_fav_pattern')]

class FavoriteStock(models.Model):
    GROUPS = (('DEFAULT', '默认'), ('WATCH', '观察'), ('TOP', '龙头'))
    ts_code = models.CharField(max_length=20)
    group = models.CharField(max_length=20, choices=GROUPS, default='DEFAULT')
    add_time = models.DateTimeField(auto_now_add=True)
    notes = models.CharField(max_length=100, blank=True)
    class Meta: constraints = [models.UniqueConstraint(fields=['ts_code'], name='unique_fav_stock')]

class TradeRecord(models.Model):
    TRADE_TYPES = (('BUY', '买入'), ('SELL', '卖出'))
    ts_code = models.CharField(max_length=20)
    trade_date = models.DateField()
    trade_type = models.CharField(max_length=10, choices=TRADE_TYPES)
    price = models.FloatField()
    volume = models.IntegerField(default=100)
    strategy_name = models.CharField(max_length=50, default='手动')
    pnl = models.FloatField(null=True, blank=True)
    create_time = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ['-create_time']

class SystemMessage(models.Model):
    title = models.CharField(max_length=100)
    content = models.TextField()
    related_code = models.CharField(max_length=20, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    create_time = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ['-create_time']

# 🔥 [新增] 用户策略模型
class UserStrategy(models.Model):
    name = models.CharField(max_length=100, verbose_name='策略名称')
    criteria = models.JSONField(verbose_name='筛选条件', default=dict)
    is_monitoring = models.BooleanField(default=False, verbose_name='是否监控')
    monitor_freq = models.IntegerField(default=60)
    notify_msg = models.BooleanField(default=True)
    create_time = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ['-create_time']