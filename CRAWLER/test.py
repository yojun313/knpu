from Package.ToolModule import ToolModule
import os

ToolModule_obj = ToolModule()

pathfinder_obj = ToolModule_obj.pathFinder()

mysql_obj = pathfinder_obj['MYSQL']

mysql_obj.connectDB('crawler_db')
proxy_list = mysql_obj.TableToList('proxy_list')

proxy_list = [proxy[0] for proxy in proxy_list]
print(proxy_list)