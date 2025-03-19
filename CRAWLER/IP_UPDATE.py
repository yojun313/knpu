from Package.ToolModule import ToolModule
import os

ToolModule_obj = ToolModule()

pathfinder_obj = ToolModule_obj.pathFinder()

mySQLObj = pathfinder_obj['MYSQL']
proxy_path = os.path.join(pathfinder_obj['crawler_folder_path'], '아이피샵(유동프록시).txt')

proxy_list = ToolModule_obj.read_txt(proxy_path)
proxy_list = [[proxy] for proxy in proxy_list]

print("IP 리스트 초기화 중... ", end='')
mySQLObj.connectDB('crawler_db')
mySQLObj.dropTable('proxy_list')
mySQLObj.commit()
print("완료")
print('\nIP리스트 업데이트 중... ')
mySQLObj.newTable('proxy_list', ['proxy'])
mySQLObj.insertToTable('proxy_list', proxy_list)
mySQLObj.commit()
print("완료")

print('\n\nIP 업데이트가 완료되었습니다. 아이피샵 Proxy 프로그램을 종료하지 마십시오\n현재 창은 닫아도 무방합니다')