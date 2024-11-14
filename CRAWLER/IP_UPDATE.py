from Package.ToolModule import ToolModule
import os

ToolModule_obj = ToolModule()

pathfinder_obj = ToolModule_obj.pathFinder()

mysql_obj = pathfinder_obj['MYSQL']
proxy_path = os.path.join(pathfinder_obj['crawler_folder_path'], '아이피샵(유동프록시).txt')

proxy_list = ToolModule_obj.read_txt(proxy_path)
proxy_list = [[proxy] for proxy in proxy_list]

print("IP 리스트 초기화 중... ", end='')
mysql_obj.connectDB('crawler_db')
mysql_obj.dropTable('proxy_list')
mysql_obj.commit()
print("완료")
print('\nIP리스트 업데이트 중... ')
mysql_obj.newTable('proxy_list', ['proxy'])
mysql_obj.insertToTable('proxy_list', proxy_list)
mysql_obj.commit()
print("완료")

print('\n\nIP 업데이트가 완료되었습니다. 아이피샵 Proxy 프로그램을 종료하지 마십시오\n현재 창은 닫아도 무방합니다')