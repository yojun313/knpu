# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
import pymysql
import sys
from datetime import date, timedelta
import socket
import datetime
import random
import urllib3
from user_agent import generate_user_agent, generate_navigator
import os
import requests
import json
import random
import pandas as pd
import platform
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service  
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials
import pickle
import io


'''
def parseNews(url):
    oid = url[39:42]
    aid = url[43:53]
    page = 1
    
    navigator = generate_navigator()
    
    navigator = navigator['user_agent']
    headers = { 
    "User-agent":navigator, 
    "referer":url, 
    }  
    
    params = {
                'ticket': 'news',
                'templateId': 'default_society',
                'pool': 'cbox5',
                'lang': 'ko',
                'country': 'KR',
                'objectId': f'news{oid},{aid}',
                'pageSize': '100',
                'indexSize': '10',
                'page': str(page),
                'currentPage': '0',
                'moreParam.direction': 'next',
                'moreParam.prev': '10000o90000op06guicil48ars',
                'moreParam.next': '1000050000305guog893h1re',
                'followSize': '100',
                'includeAllStatus': 'true',
                'sort': 'reply'
             }
    # https://apis.naver.com/commentBox/cbox/web_naver_list_jsonp.json?ticket=news&templateId=view_society_m1&pool=cbox5&_cv=20240319154009&_callback=jQuery33108435267684748844_1711115022097&lang=ko&country=KR&objectId=news001%2C0014581332&categoryId=&pageSize=5&indexSize=10&groupId=&listType=OBJECT&pageType=more&page=1&initialize=true&followSize=5&userType=&useAltSort=true&replyPageSize=20&sort=FAVORITE&includeAllStatus=true&_=1711115022101
    #response = requests.get('https://apis.naver.com/commentBox/cbox/web_naver_list_jsonp.json', params=params, headers=headers)
    response = requests.get("https://apis.naver.com/commentBox/cbox/web_naver_list_jsonp.json?ticket=news&templateId=view_society_m1&pool=cbox5&_cv=20240319154009&_callback=jQuery33108435267684748844_1711115022097&lang=ko&country=KR&objectId=news001%2C0014581332&categoryId=&pageSize=5&indexSize=10&groupId=&listType=OBJECT&pageType=more&page=1&initialize=true&followSize=5&userType=&useAltSort=true&replyPageSize=20&sort=FAVORITE&includeAllStatus=true&_=1711115022101", headers = headers)
    response.encoding = "UTF-8-sig"
    res = response.text.replace("_callback(","")[:-2]
    temp=json.loads(res)
    print(temp)

parseNews("https://n.news.naver.com/mnews/article/001/0014581332?sid=102")
'''


#이거 작동됨

def parsetest(url):
    
    oid = url[39:42]
    aid = url[43:53]

    basic_url = "https://apis.naver.com/commentBox/cbox/web_naver_list_jsonp.json"
    params = {
        'ticket': 'news',
        'pool': 'cbox5',
        'lang': 'ko',
        'country': 'KR',
        'objectId':  f'news{oid},{aid}',
        'pageSize': '100',
        'indexSize': '10',
        'page': '1',
        'initialize': 'true',
        'followSize': '100',
        'userType': '',
        'useAltSort': 'true',
        'replyPageSize': '20',
        'sort': 'reply',
        'includeAllStatus': 'true',
        'moreParam.direction': 'next',
        'moreParam.prev': '10000o90000op06guicil48ars',
        'moreParam.next': '1000050000305guog893h1re',
    }
    headers = { 
    "User-agent":'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36', 
    "referer":url, 
    }  

    response = requests.get(basic_url, params=params, headers=headers)
    response.encoding = "UTF-8-sig"
    #res = response.text.replace("_callback(","")[:-2]
    #temp = json.loads(res)
    #temp=json.loads(res)
    print(response.text)

parsetest("https://n.news.naver.com/mnews/article/001/0014581332?sid=102")
#parsetest("https://n.news.naver.com/mnews/article/001/0014581987?sid=102")#작동됨