def mark_dangerous_words(word_list, text):
    is_dangerous = False
    for word in word_list:
        if word in text:
            text = text.replace(word, f"{word}(Danger)")
            is_dangerous = True
    return is_dangerous, text

# 예제 사용법
words = ["단어1", "단어2", "단어3"]
input_text = "이 문장에는 단어1이 포함되어 있습니다."

is_dangerous, result = mark_dangerous_words(words, input_text)
print(is_dangerous)  # True
print(result)  # 이 문장에는 단어1(Danger)이 포함되어 있습니다.