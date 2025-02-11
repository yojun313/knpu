import requests
from user_agent import generate_navigator
import json

newsURL = "https://n.news.naver.com/mnews/article/comment/015/0003164210?sid=102"
headers = {"User-agent":generate_navigator()['user_agent'], "referer":newsURL}
def ReplyUsername(oid, aid, commentNo):
    # API 엔드포인트
    url = "https://apis.naver.com/commentBox/cbox/web_naver_user_info_jsonp.json"
    # 요청 파라미터
    params = {
        "ticket": "news",
        "templateId": "default_society",
        "pool": "cbox5",
        "lang": "ko",
        "country": "KR",
        "objectId": f'news{oid},{aid}',
        "categoryId": "",
        "pageSize": 20,
        "indexSize": 10,
        "groupId": "",
        "listType": "user",
        "pageType": "more",
        "commentNo": commentNo,
        "targetUserInKey": "",
        "_": "1739271277330"
    }


    # GET 요청 보내기
    response = requests.get(url, params=params, headers=headers).text
    res = '{' + response.replace("_callback(", "")[:-2].split("{", 1)[-1]
    data = json.loads(res)

    nickname   = data['result']['user']['nickname']
    commentCnt = data['result']['commentUserStats']['commentCount']
    replyCnt   = data['result']['commentUserStats']['replyCount']
    likecnt    = data['result']['commentUserStats']['sympathyCount']

    return [nickname, commentCnt, replyCnt, likecnt]

ReplyUsername('015', '0003164210', 62344684)