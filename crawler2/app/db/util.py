from datetime import datetime, timedelta, timezone

def makeDBname(type, keyword, startDate, endDate):
    replacements = {
            '\\': '＼',  # U+FF3C
            '/': '／',   # U+FF0F
            ':': '：',   # U+FF1A
            '*': '＊',   # U+FF0A
            '?': '？',   # U+FF1F
            '"': '＂',   # U+FF02
            '<': '＜',   # U+FF1C
            '>': '＞',   # U+FF1E
            '|': '¦',    # U+00A6
        }

    for illegal, safe in replacements.items():
        keyword = keyword.replace(illegal, safe)
        
    now_kst = datetime.now(timezone.utc).astimezone(
        timezone(timedelta(hours=9))
    ).strftime('%m%d_%H%M')
    
    DBname = f"{type}_{keyword}_{startDate}_{endDate}_{now_kst}"        
    return DBname