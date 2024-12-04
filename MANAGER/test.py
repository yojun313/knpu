import pyttsx3

def speecher(text):
    try:
        # pyttsx3 엔진 초기화
        engine = pyttsx3.init()

        # 사용 가능한 음성 확인 및 설정
        voices = engine.getProperty('voices')
        for voice in voices:
            print(f"Available voice: {voice.name} - {voice.languages}")

        # 적절한 음성 선택 (여기서는 첫 번째 음성 선택)
        engine.setProperty('voice', voices[0].id)  # 필요한 경우 index 변경

        # 속도와 볼륨 설정
        engine.setProperty('rate', 150)  # 속도
        engine.setProperty('volume', 1.0)  # 볼륨

        # 텍스트 음성 변환 및 출력
        engine.say(text)
        engine.runAndWait()

    except Exception as e:
        print(f"오류가 발생했습니다: {e}")

# 테스트
speecher("안녕하세요. 테스트입니다.")
