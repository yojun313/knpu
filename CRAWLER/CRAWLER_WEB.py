import CRAWLER
import sys

def control():
    
    print("================ Crawler Controller ================\n")
    name = input("본인의 이름을 입력하세요: ")
    print("\n크롤링 대상\n")
    print("1. 네이버 뉴스\n2. 네이버 블로그\n3. 유튜브\n4. 프로그램 종료")
    
    while True:
        control_ask = int(input("\n입력: "))
        if control_ask in [1,2,3,4]:
            break
        else:
            print("다시 입력하세요")
            
    start     = input("\nStart Date (ex: 20230101): ") 
    end       = input("End Date (ex: 20231231): ") 
    keyword   = input("\nKeyword: ")
    
    print("\n1. 기사 \n2. 기사 + 댓글\n3. 기사 + 댓글 + 대댓글\n")
    while True:
        option = int(input("Option: "))
        if option in [1,2,3]:
            break
        else:
            print("다시 입력하세요")
    
    upload    = input("\n구글 드라이브에 업로드 하시겠습니까(Y/N)? ")
    
    
    print("\n====================================================")
    
    if control_ask == 1:
        crawler = CRAWLER.Crawler(name, start, end, keyword, upload)
        crawler.crawl_news(option)
    
    elif control_ask == 2:
        crawler = CRAWLER.Crawler(name, start, end, keyword, upload)
        crawler.crawl_blog(option)
        
    elif control_ask == 3:
        crawler = CRAWLER.Crawler(name, start, end, keyword, upload)
        crawler.crawl_youtube(option)
    
    else:
        sys.exit()
            
control()