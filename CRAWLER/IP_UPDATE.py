import os
import sys
import chardet

CRAWLER_PATH = os.path.dirname(os.path.abspath(__file__))
BIGMACLAB_PATH      = os.path.dirname(CRAWLER_PATH)
MANAGER_PATH          = os.path.join(BIGMACLAB_PATH, 'MANAGER')

sys.path.append(MANAGER_PATH)

from mySQL import mySQL

def read_txt(filepath):
    result_list = []

    # 파일의 일부만 읽어 인코딩 감지
    with open(filepath, 'rb') as file:
        raw_data = file.read(10240)  # 처음 10KB만 읽음
        result = chardet.detect(raw_data)
        charenc = result['encoding']

    # 감지된 인코딩을 사용하여 파일을 텍스트 모드로 읽기
    with open(filepath, 'r', encoding=charenc) as f:
        lines = f.readlines()

    result_list = [line.strip() for line in lines]
    return result_list

mysql_obj = mySQL(host='121.152.225.232', user='admin', password='bigmaclab2022!', port=3306)
proxy_path = os.path.join("D:/BIGMACLAB/CRAWLER", '아이피샵(유동프록시).txt')

print("MYSQL 접속 완료\n")

proxy_list = read_txt(proxy_path)
proxy_list = [[proxy.strip()] for proxy in proxy_list]

print("IP 리스트 초기화 중... ", end='')
mysql_obj.connectDB('crawler_db')
mysql_obj.dropTable('proxy_list')
mysql_obj.commit()
print("완료")
print('\nIP리스트 업데이트 중... ', end='')
mysql_obj.newTable('proxy_list', ['proxy'])
mysql_obj.insertToTable('proxy_list', proxy_list)
mysql_obj.commit()
print("완료")

print('\n\nIP 업데이트가 완료되었습니다. 아이피샵 Proxy 프로그램을 종료하지 마십시오\n현재 창은 닫아도 무방합니다')