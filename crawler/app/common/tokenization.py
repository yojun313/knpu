from kiwipiepy import Kiwi
import time
import re
import os
import pandas as pd

def tokenization(data: pd.DataFrame, language='ko'):
    if language == 'en':
        import nltk
        from nltk.tokenize import word_tokenize
        from nltk.tag import pos_tag
        nltk_path = os.path.join(os.getenv('MODEL_PATH'), 'nltk_data')
        if nltk_path not in nltk.data.path:
            nltk.data.path.append(nltk_path)

    kiwi = Kiwi(num_workers=-1) if language == 'ko' else None
    
    textColumn_name = ""
    for column in data.columns.tolist():
        if 'Text' in column:
            textColumn_name = column
            break

    text_list = list(data[textColumn_name])
    tokenized_data = []
    total_texts = len(text_list)
    total_time = 0

    for index, text in enumerate(text_list):
        start_time = time.time()

        try:
            if not isinstance(text, str):
                tokenized_data.append("")
                continue

            if language == 'ko':
                text = re.sub(r'[^가-힣a-zA-Z\s]', '', text)
                tokens = kiwi.tokenize(text, split_complex=False)
                tokenized_text = [token.form for token in tokens if token.tag in ('NNG', 'NNP')]
            else:
                text = re.sub(r'[^a-zA-Z\s]', '', text)
                tokens = word_tokenize(text)
                tagged = pos_tag(tokens)
                tokenized_text = [word for word, tag in tagged if tag in ('NN', 'NNS', 'NNP', 'NNPS')]

            tokenized_text_str = ", ".join(tokenized_text)
            tokenized_data.append(tokenized_text_str)

        except Exception:
            tokenized_data.append("")

        end_time = time.time()
        total_time += end_time - start_time

        avg_time_per_text = total_time / (index + 1)
        remaining_time = avg_time_per_text * (total_texts - (index + 1))
        remaining_minutes = int(remaining_time // 60)
        remaining_seconds = int(remaining_time % 60)

        update_interval = 500
        if (index + 1) % update_interval == 0 or index + 1 == total_texts:
            progress_value = round((index + 1) / total_texts * 100, 2)
            '''
            print(
                f'\r{textColumn_name.split(" ")[0]} ({language}) Tokenization Progress: {progress_value}% | '
                f'예상 남은 시간: {remaining_minutes}분 {remaining_seconds}초', end=''
            )
            '''
    data[textColumn_name] = tokenized_data
    return data