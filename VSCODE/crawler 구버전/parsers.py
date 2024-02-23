import requests
from bs4 import BeautifulSoup
import re
import sys
import json
from dbapi import DBConnector
import jsonify


def writeLog(msg):
    f = open("./log.txt", "a")
    msg += "\n\n"
    f.write(msg)
    f.close()


def parseSports(url):
    try:
        header = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
        }
        res = requests.get(url=url, headers=header)
        bs = BeautifulSoup(res.content, "html.parser")
        press_element = bs.find("span", id="pressLogo")
        press = press_element.find("img")["alt"]

    except Exception as e:
        _, _, tb = sys.exc_info()  # tb -> traceback object
        msg = (
            "File name: "
            + __file__
            + "\n"
            + "Error line= {}".format(tb.tb_lineno)
            + "\n"
            + "Error: {}".format(sys.exc_info()[0])
            + " "
            + str(e)
        )
        print(msg)
        writeLog(msg)
    return


def parseEntertain(url):
    try:
        header = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
        }
        res = requests.get(url=url, headers=header)
        bs = BeautifulSoup(res.content, "html.parser")
        press_element = bs.find("a", class_="press_logo")
        press = press_element.find("img")["alt"]
    except Exception as e:
        _, _, tb = sys.exc_info()  # tb -> traceback object
        msg = (
            "File name: "
            + __file__
            + "\n"
            + "Error line= {}".format(tb.tb_lineno)
            + "\n"
            + "Error: {}".format(sys.exc_info()[0])
            + " "
            + str(e)
        )
        print(msg)
        writeLog(msg)

    return


def parseNews(url, connector, OPTION):
    try:
        dbconn = connector

        header = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
        }
        data = {
            "article_press": None,
            "article_type": None,
            "url": None,
            "article_title": None,
            "article_body": None,
            "article_date": None,
            "R_count": None,
            "male": None,
            "female": None,
            "tens": None,
            "twentys": None,
            "thirtys": None,
            "fortys": None,
            "fiftys": None,
            "sixtys": None,
        }
        data["url"] = url
        res = requests.get(url=url, headers=header)
        bs = BeautifulSoup(res.content, "html.parser")

        press_element = bs.find("img", class_=re.compile("media_end_head"))
        # article_press
        data["article_press"] = press_element["title"]

        # article_type
        data["article_type"] = bs.find("em", class_="media_end_categorize_item").text

        # article_title
        data["article_title"] = bs.find("div", class_="media_end_head_title").text

        # article_body
        data["article_body"] = bs.find("div", class_=re.compile("newsct_article")).text

        # article_date
        data["article_date"] = bs.find("span", class_=re.compile("_ARTICLE_DATE_TIME"))[
            "data-date-time"
        ]

        # R_count
        data["R_count"] = bs.find("span", class_="u_cbox_count")
        


        # print(json.dumps(data, ensure_ascii=False))

        article_id = dbconn.insertNaverArticleData(data=data)

        if OPTION == 1:
            return

        ##### Comment parse

        oid = url.split("?")[0].split("/")[-2]
        aid = url.split("?")[0].split("/")[-1]
        # print(oid, aid)
        page = 1
        header = {
            "User-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36",
            "Referer": url,
        }
        base_url = "".join(
            [
                "https://apis.naver.com/commentBox/cbox/web_naver_list_jsonp.json?ticket=news",
                "&pool=cbox5&lang=ko&country=KR",
                "&objectId=news{}%2C{}&categoryId=&pageSize={}&indexSize=10&groupId=&listType=OBJECT&pageType=more",
                "&page={}&initialize=true&followSize=5&userType=&useAltSort=true&replyPageSize=20&sort={}&includeAllStatus=true&_=1696730082374",
            ]
        )

        base_url_tmp = base_url.format(oid, aid, 10, 1, "favorite")
        r = requests.get(base_url_tmp, headers=header)
        html = r.text

        html = html[10:-2]

        response = json.loads(html)

        # print(base_url_tmp)
        # print(ex)
        n_comments = response.get("result", {}).get("count", {}).get("comment", 0)

        max_page = round(n_comments / 100 + 0.5)
        if max_page <= 0:
            return []

        commentCount = 0
        try:
            for page in range(1, max_page + 1):
                base_url_tmp = base_url.format(oid, aid, 100, page, "reply")
                r = requests.get(base_url_tmp, headers=header)
                html = r.text
                # print(html)
                html = html[10:-2]
                response = json.loads(html)

                print("\n\n")

                reply_idx = 0
                for comment_json in response.get("result", {}).get("commentList", []):
                    reply_idx += 1
                    # user_id, reply_count, parentCommentNo, contents, reg_time, sympathy_count, antipathy_count
                    parse_result = _parse_comment(comment_json)
                    print(parse_result)
                    nickName = parse_result[0]
                    replyDate = parse_result[4]
                    text = (
                        parse_result[3]
                        .encode("cp949", "ignore")
                        .decode("cp949", "ignore")
                    )
                    rere_count = parse_result[1]
                    r_like = parse_result[5]
                    r_bad = parse_result[6]
                    # 댓글 긍정 지수 구하기
                    r_per_like = 0.0
                    r_sum_like_angry = int(r_like) + int(r_bad)
                    if r_sum_like_angry != 0:
                        r_per_like = float(int(r_like) / r_sum_like_angry)
                        r_per_like = float(format(r_per_like, ".2f"))

                    # 댓글 긍정,부정 평가
                    if r_per_like > 0.5:  # 긍정
                        r_sentiment = 1
                    elif r_per_like == 0:  # 무관심
                        r_sentiment = 2
                    elif r_per_like < 0.5:  # 부정
                        r_sentiment = -1
                    else:  # 중립
                        r_sentiment = 0

                    # 댓글 집어넣기
                    repleLastIndex = dbconn.insertNaverReplyData(
                        str(article_id),
                        str(reply_idx),
                        str(nickName),
                        str(replyDate),
                        str(text),
                        str(rere_count),
                        str(r_like),
                        str(r_bad),
                        str(r_per_like),
                        str(r_sentiment),
                    )
                    print(repleLastIndex)
                    # 대댓글 개수가 0개 이상이면 parentCommentNo추가해서 한번 더 크롤링
                    if OPTION == 2:
                        continue
                    
                    if rere_count > 0:
                        # 대댓글을 100개씩 뿌릴때
                        maxRepage = round(rere_count / 20 + 0.5)
                        for rePage in range(1, maxRepage + 1):
                            base_url_tmp_re = (
                                base_url.format(oid, aid, 20, rePage, "reply")
                                + "&parentCommentNo="
                                + str(parse_result[2])
                            )
                            # base_url_tmp_re = '&parentCommentNo='+parse_result[2]+'&page='+rePage
                            re_r = requests.get(base_url_tmp_re, headers=header)
                            re_html = re_r.text.encode("cp949", "ignore").decode(
                                "cp949", "ignore"
                            )
                            re_html = re_html[10:-2]
                            re_response = json.loads(re_html)

                            # 대댓글 분석 시작
                            rereply_idx = 0
                            for rereply_json in re_response.get("result", {}).get(
                                "commentList", []
                            ):
                                rereply_idx += 1

                                # user_id, reply_count, parentCommentNo, contents, reg_time, sympathy_count, antipathy_count
                                re_parse_result = _parse_comment(rereply_json)
                                print("+--->", re_parse_result)
                                # 대댓글 집어넣기
                                nickName2 = re_parse_result[0]
                                replyDate2 = re_parse_result[4]
                                text2 = re_parse_result[3]
                                rere_like = re_parse_result[5]
                                rere_bad = re_parse_result[6]

                                dbconn.insertNaverReReplyData(
                                    str(article_id),
                                    str(repleLastIndex),
                                    str(rereply_idx),
                                    nickName2,
                                    str(replyDate2),
                                    text2,
                                    str(rere_like),
                                    str(rere_bad),
                                )
                    # else:
                    #     # 대댓글이 존재하지 않으면
                    #     # 그냥 기사정보. 댓글정보만을 모아서 DB에 저장
                    #     total_sentiment = sentiment * r_sentiment
                    #     dbconn.insertNaverTotalData(str(current_index), str(press), article_type, url, str(title), str(article_date), str(body), str(like), str(angry), str(per_like), str(sentiment), str(re_Count), str(repleLastIndex), str(nickName), str(
                    #         text), str(rere_count), str(r_like), str(r_bad), str(r_per_like), str(r_sentiment), str(-1), '', '', '0', '0', str(total_sentiment), str(male), str(female), str(tens), str(twentys), str(thirtys), str(fortys), str(fiftys), str(sixty))
                    commentCount += 1

        except Exception as e:
            _, _, tb = sys.exc_info()  # tb -> traceback object
            msg = (
                "File name: "
                + __file__
                + "\n"
                + "Error line= {}".format(tb.tb_lineno)
                + "\n"
                + "Error: {}".format(sys.exc_info()[0])
                + " "
                + str(e)
            )
            print(msg)
            writeLog(msg)

        print("Total:comment", commentCount)

    except Exception as e:
        _, _, tb = sys.exc_info()  # tb -> traceback object
        msg = (
            "File name: "
            + __file__
            + "\n"
            + "Error line= {}".format(tb.tb_lineno)
            + "\n"
            + "Error: {}".format(sys.exc_info()[0])
            + " "
            + str(e)
        )
        print(msg)
        writeLog(msg)

    return


def _parse_comment(comment_json):
    antipathy_count = comment_json["antipathyCount"]
    sympathy_count = comment_json["sympathyCount"]
    contents = (
        comment_json["contents"]
        .replace("\t", " ")
        .replace("\r", " ")
        .replace("\n", " ")
        .encode("cp949", "ignore")
        .decode("cp949", "ignore")
    )
    reg_time = comment_json["regTime"]
    user_id = (
        comment_json["userName"].encode("cp949", "ignore").decode("cp949", "ignore")
    )

    reply_count = comment_json["replyCount"]
    parentCommentNo = comment_json["parentCommentNo"]

    return (
        user_id,
        reply_count,
        parentCommentNo,
        contents,
        reg_time,
        sympathy_count,
        antipathy_count,
    )


def getURLs(keyword, currentDate, connector, OPTION):
    try:
        search_page_url = "https://search.naver.com/search.naver?where=news&query={}&sm=tab_srt&sort=2&photo=0&reporter_article=&pd=3&ds={}&de={}&&start={}&related=0"
        currentPage = 1
        # 키워드, 현재날짜, 서치 페이지 로 검색결과 가져오기
        search_page_url_firstpage = search_page_url.format(
            keyword, currentDate, currentDate, currentPage
        )
        print(search_page_url_firstpage)

        r = requests.get(search_page_url_firstpage)
        html = r.content
        soup = BeautifulSoup(html, "html.parser")

        # 전체 개수
        totalCount = soup.find_all(id=re.compile("sp_nws"), class_="bx")
        naverCount = soup.find_all(href=re.compile("news.naver.com"), class_="info")
        print("총 갯수! : ", len(totalCount))
        print("네이버 총 갯수! : ", len(naverCount))

        if len(totalCount) == 0:
            return

        # 현재 검색페이지가 전체 개수보다 작을동안
        while len(totalCount) > 0:
            urlList = []
            search_page_url_tmp = search_page_url.format(
                keyword, currentDate, currentDate, currentPage
            )
            print(search_page_url_tmp)

            r = requests.get(search_page_url_tmp)
            html = r.content
            soup = BeautifulSoup(html, "html.parser")

            # 전체 기사 갯수
            totalCount = soup.find_all(id=re.compile("sp_nws"), class_="bx")
            if len(totalCount) == 0:
                print("Daily crawl done.")
                break

            # 네이버 기사 찾기
            current_page_urls = soup.find_all(
                href=re.compile("news.naver.com"), class_="info"
            )

            count = 0
            for item in current_page_urls:
                # print()
                tmpUrl = item["href"]
                urlList.append(tmpUrl)
                count += 1

            # URL들에 대해 기사 파싱
            for url in urlList:
                if "entertain" in url:
                    pass
                elif "sports" in url:
                    pass
                else:
                    success = parseNews(url, connector,OPTION)

            # 다음페이지 이동
            currentPage += 10
            print("Current Page : ", currentPage)

        print("getURL Done.")

    except Exception as e:
        _, _, tb = sys.exc_info()  # tb -> traceback object
        msg = (
            "File name: "
            + __file__
            + "\n"
            + "Error line= {}".format(tb.tb_lineno)
            + "\n"
            + "Error: {}".format(sys.exc_info()[0])
            + " "
            + str(e)
        )
        print(msg)
        writeLog(msg)

    return 0
