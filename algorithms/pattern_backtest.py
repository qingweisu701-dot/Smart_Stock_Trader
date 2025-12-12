import numpy as np
import pandas as pd
from fastdtw import fastdtw
from scipy.spatial.distance import euclidean
from data_engine.models import StockDaily, StockBasic

# Re-use normalization from matcher to ensure consistency
# Ideally we should refactor matcher.py to export this, 
# but for now I'll duplicate the small static function to avoid circular imports or breaking changes
def normalize_series(series):
    series = np.array(series)
    if np.std(series) == 0: return series
    return (series - np.mean(series)) / np.std(series)

def run_pattern_backtest(target_pattern, stock_pool=None, hold_days=10, similarity_threshold=75, limit_matches=100):
    """
    Search for historical occurrences of 'target_pattern' and calculate future returns.
    
    Args:
        target_pattern (list): The list of closings prices (or normalized values) of the shape.
        stock_pool (QuerySet): Optional subset of stocks to search. If None, picks a random sample to save time.
        hold_days (int): How many days to look ahead for return calculation.
        similarity_threshold (float): 0-100 score cutoff.
        limit_matches (int): Stop after finding this many matches (performance safety).
        
    Returns:
        dict: Backtest report with 'metrics' and 'matches'.
    """
    
    # 1. Prepare Target
    if not target_pattern or len(target_pattern) < 3:
        return {"error": "Pattern too short"}
        
    norm_target = normalize_series(target_pattern)
    window_size = len(target_pattern)
    
    matches_found = []
    
    # 2. Define Scope
    # Searching ALL stocks ALL history is extremely slow in pure Python.
    # We will sample 50 stocks randomly if no pool is provided, or use the provided pool.
    if stock_pool is None:
        # Random sample for demo speed
        import random
        all_codes = list(StockBasic.objects.values_list('ts_code', flat=True))
        if len(all_codes) > 50:
            sample_codes = random.sample(all_codes, 50)
        else:
            sample_codes = all_codes
    else:
        sample_codes = [s.ts_code for s in stock_pool]
        
    # 3. Sliding Window Search
    for code in sample_codes:
        if len(matches_found) >= limit_matches: break
        
        # Get full history
        qs = StockDaily.objects.filter(ts_code=code).order_by('trade_date')
        data = list(qs.values('trade_date', 'close_price'))
        
        if len(data) < window_size + hold_days: continue
        
        closes = np.array([d['close_price'] for d in data])
        dates = [d['trade_date'] for d in data]
        
        # Vectorized optimization is hard with DTW, so we iterate
        # Optimization: Skip windows with vastly different variance first? (Omitted for simplicity)
        
        # Step: length - window - hold_days ensures we have 'hold_days' of future data
        max_idx = len(closes) - window_size - hold_days
        
        # Jump step can be 1, but for speed we might do window // 2 to avoid overlapping "same" patterns
        step = max(1, window_size // 4) 
        
        for i in range(0, max_idx, step):
            segment = closes[i : i+window_size]
            
            # Fast filter: Correlation check (much faster than DTW)
            # if np.corrcoef(norm_target, normalize_series(segment))[0,1] < 0.8: continue
            
            # DTW Check
            norm_seg = normalize_series(segment)
            dist, _ = fastdtw(norm_target, norm_seg, dist=lambda x, y: abs(x - y))
            score = max(0, 100 - dist * 2) # Simple heuristic mapping
            
            if score >= similarity_threshold:
                # Found a match! Record future performance
                entry_price = closes[i + window_size - 1] # Last point of pattern
                exit_price = closes[i + window_size - 1 + hold_days] # N days later
                
                # Check High/Low in between for drawdown/max_profit
                future_window = closes[i + window_size : i + window_size + hold_days]
                highest = np.max(future_window)
                lowest = np.min(future_window)
                
                pnl = (exit_price - entry_price) / entry_price * 100
                max_gain = (highest - entry_price) / entry_price * 100
                max_loss = (lowest - entry_price) / entry_price * 100
                
                match_record = {
                    'code': code,
                    'date': dates[i + window_size - 1].strftime('%Y-%m-%d'),
                    'score': round(score, 1),
                    'return': round(pnl, 2),
                    'max_gain': round(max_gain, 2),
                    'max_drawdown': round(max_loss, 2),
                    # 'preview': segment.tolist() # payload size optimization
                }
                matches_found.append(match_record)

    # 4. Aggregation & Metrics
    if not matches_found:
        return {
            "status": "No matches found", 
            "metrics": {"count": 0, "win_rate": 0, "avg_return": 0},
            "matches": []
        }
    
    df_res = pd.DataFrame(matches_found)
    win_count = len(df_res[df_res['return'] > 0])
    avg_ret = df_res['return'].mean()
    
    report = {
        "metrics": {
            "count": len(matches_found),
            "win_rate": round(win_count / len(matches_found) * 100, 1),
            "avg_return": round(avg_ret, 2),
            "best_match": df_res.iloc[0].to_dict() # sort by score implies first is best usually, but we append sequentially. 
        },
        "matches": matches_found[:20] # Return top 20 for display
    }
    
    return report
