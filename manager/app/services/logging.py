from services.api import Request
import traceback
from ui.status import printStatus
from PyQt6.QtWidgets import QMessageBox
from config import VERSION
import requests

def userLogging(text=''):
    try:
        jsondata = {
            "message": text
        }
        Request('post', '/users/log', json=jsondata)
    except Exception as e:
        print(traceback.format_exc())


def userBugging(text=''):
    try:
        jsondata = {
            "message": text
        }
        Request('post', '/users/bug', json=jsondata)
    except Exception as e:
        print(traceback.format_exc())

def programBugLog(parent, text):
    print(text)
    printStatus(parent, "오류 발생")
    QMessageBox.critical(parent, "Error", f"오류가 발생했습니다\n\nError Log: {text}")

    userBugging(text)

    reply = QMessageBox.question(parent, 'Bug Report', "버그 리포트를 전송하시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                    QMessageBox.StandardButton.Yes)
    if reply == QMessageBox.StandardButton.Yes:
        parent.managerBoardObj.addBug()

    printStatus(parent)

def getUserLocation(parent, detail=False):
    try:
        response = requests.get("https://ipinfo.io")
        data = response.json()
        returnData = f"{VERSION} | {parent.userDevice} | {data.get("ip")} | {data.get("city")}"
        if detail == True:
            returnData = f"{data.get("ip")} | {data.get("city")} | {data.get('region')} | {data.get('country')} | {data.get('loc')} | {VERSION}"
        return returnData
    except requests.RequestException as e:
        return ""
