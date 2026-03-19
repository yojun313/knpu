def makeDBname(keyword):
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
        
    return keyword