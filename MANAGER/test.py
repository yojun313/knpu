from pyfingerprint.pyfingerprint import PyFingerprint

try:
    # 지문 센서 초기화
    sensor = PyFingerprint('/dev/ttyUSB0', 57600, 0xFFFFFFFF, 0x00000000)

    if sensor.verifyPassword():
        print('지문 센서 초기화 성공')

    # 지문 등록 프로세스
    print('지문을 스캔하세요...')
    while not sensor.readImage():
        pass

    # 지문 템플릿 저장
    sensor.convertImage(0x01)
    position = sensor.storeTemplate()
    print(f'지문이 성공적으로 저장되었습니다. 위치: {position}')

except Exception as e:
    print(f'오류 발생: {e}')
