from django.contrib import admin
from .models import StockDaily, TradeRecord

@admin.register(StockDaily)
class StockDailyAdmin(admin.ModelAdmin):
    # 注意：这里改成了 close_price 以匹配 model 字段
    list_display = ('ts_code', 'trade_date', 'close_price', 'vol', 'amount')
    search_fields = ('ts_code',)
    list_filter = ('trade_date',)

@admin.register(TradeRecord)
class TradeRecordAdmin(admin.ModelAdmin):
    # 这里修改为 TradeRecord 实际拥有的字段
    list_display = ('ts_code', 'trade_date', 'trade_type', 'price', 'volume', 'strategy_name', 'create_time')
    list_filter = ('trade_type', 'strategy_name', 'trade_date')
    search_fields = ('ts_code',)