import re

text = '<a href="https://www.youtube.com/watch?v=l3Kq52MjDII&amp;t=605">10:05</a> 어우 세대 차이를 이렇게 가감없이 보여주시면 ㅋㅋㅋ'

# 정규 표현식 패턴
pattern = r'<a[^>]*>(.*?)<\/a>'

# 패턴에 맞는 부분을 교체
result = re.sub(pattern, '', text)

print(result[1:])