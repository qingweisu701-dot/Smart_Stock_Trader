from django.contrib import admin
from .models import StockDaily, TradeRecord

@admin.register(StockDaily)
class StockDailyAdmin(admin.ModelAdmin):
    list_display = ('ts_code', 'trade_date', 'close', 'vol')
    search_fields = ('ts_code',)
    list_filter = ('trade_date',)

# 新增这一段
@admin.register(TradeRecord)
class TradeRecordAdmin(admin.ModelAdmin):
    list_display = ('ts_code', 'trade_type', 'price', 'volume', 'strategy_name', 'create_time')
    list_filter = ('trade_type', 'strategy_name')
    search_fields = ('ts_code',)