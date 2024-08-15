

import urllib.parse

# 인코딩할 문자열
original_string = "테러 +예고"

# URL 인코딩 (공백을 +로)
encoded_string = urllib.parse.quote_plus(original_string)

print(encoded_string)
