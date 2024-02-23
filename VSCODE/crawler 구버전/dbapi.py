import pymysql
import sys
 

class DBConnector:

    global conn
    dbname = ''
    # SQL접속 초기화. MySql에 접속하는 부분
    # password를 바꿔줘야 함.
    def init(self):
        try:
            # self.conn = pymysql.connect(host='147.43.122.131', user='root', password='1234', charset='utf8')    
            self.conn = pymysql.connect(host='127.0.0.1', user='root', password='uxil1234', charset='utf8')    
            print("Initialize connect.")
        except Exception as e:
            print('Connection Error : ', e)
        return
    
    def initialize(self, dbname):
        
        self.createNaverDatabase(dbname)
        self.createNaverArticleTable(dbname)
        self.createNaverReplyTable(dbname)
        self.createNaverReReplyTable(dbname)
    
    def connect(self):
        try:
            # self.conn = pymysql.connect(host='147.43.122.131', user='root', password='1234', charset='utf8')    
            self.conn = pymysql.connect(host='127.0.0.1', user='root', password='1234', charset='utf8')    
        except Exception as e:
            print('Connection Error : ', e)
        return

    def setDBName(self, name):
        self.dbname = name

    #Naver뉴스 DB생성(NaverNews_DB) 함수
    def createNaverDatabase(self,dbname ):
        try:
            self.dbname = dbname
            self.connect()
            curs = self.conn.cursor() #cursor = 데이터베이스 쿼리를 실행하고 결과를 관리하는 객체, curs변수에 생성
            #NaverNews_DB를 생성하는 쿼리
            query = """CREATE DATABASE """+dbname # 데이터 베이스 생성
            curs.execute(query) # query를 excute
            print('DB를 생성. DB_NAME :' , dbname)
            self.conn.commit()    

            # NaverNews_DB의 문자세트를 utf8로 변환
            query = """ALTER DATABASE """+ dbname + """ CHARACTER SET utf8 COLLATE utf8_general_ci;"""
            curs.execute(query)
            self.conn.commit()
            self.conn.close()

        except Exception as e:
            _, _, tb = sys.exc_info()  # tb -> traceback object
            msg = 'File name: ' + __file__ + '\n' + 'Error line= {}'.format(tb.tb_lineno) + '\n' + 'Error: {}'.format(sys.exc_info()[0]) + ' '+str(e)
            print(msg)
            self.conn.close()

    #Naver뉴스 Table 생성 함수
    def createNaverArticleTable(self, dbname):
        self.connect()
        curs = self.conn.cursor()
        query = """use """+dbname
        curs.execute(query)
        self.conn.commit()
        #NaverNews라는 ID, URL, TITLE 등등을 포함하는 테이블을 생성
        query = """create table naver_articles(   
                                            article_id int not null auto_increment primary key,
                                            article_press varchar(50),
                                            article_type varchar(11), 
                                            url text, 
                                            article_title text, 
                                            article_body text,
                                            article_date varchar(50),
                                            R_count int,
                                            male varchar(11),
                                            female varchar(11),
                                            tens varchar(11),
                                            twentys varchar(11),
                                            thirtys varchar(11),
                                            fortys varchar(11),
                                            fiftys varchar(11),
                                            sixtys varchar(11)
                                            )"""
        try:
            curs.execute(query)
            self.conn.commit()
            query = """ALTER TABLE naver_articles CHARACTER SET utf8 COLLATE utf8_general_ci;"""
            curs.execute(query)
            self.conn.commit()
            self.conn.close()
        except Exception as e :
            _, _, tb = sys.exc_info()  # tb -> traceback object
            msg = 'File name: ' + __file__ + '\n' + 'Error line= {}'.format(tb.tb_lineno) + '\n' + 'Error: {}'.format(sys.exc_info()[0]) + ' '+str(e)
            print(msg) 
            self.conn.close()
        
        return

    #Naver뉴스 댓글 Table 생성 함수
    def createNaverReplyTable(self,dbname):
        self.connect()
        curs = self.conn.cursor()
        query = """use """+dbname
        curs.execute(query)
        self.conn.commit()
        #NaverNews라는 ID, URL, TITLE 등등을 포함하는 테이블을 생성
        query = """create table naver_replies(   
                                            article_id int not null, 
                                            reply_id int not null auto_increment primary key, 
                                            writer varchar(512),
                                            reply_date varchar(50),
                                            reply text, 
                                            rere_count int,
                                            r_Like int, 
                                            r_Bad int,
                                            r_Per_Like float,
                                            r_Sentiment int,
                                            FOREIGN KEY(article_id) REFERENCES naver_articles(article_id) ON UPDATE CASCADE ON DELETE CASCADE
                                            )"""

        try:
            curs.execute(query)
            self.conn.commit()
            query = """ALTER TABLE naver_replies CHARACTER SET utf8 COLLATE utf8_general_ci;"""
            curs.execute(query)
            self.conn.commit()
            self.conn.close()
        except Exception as e :
            _, _, tb = sys.exc_info()  # tb -> traceback object
            msg = 'File name: ' + __file__ + '\n' + 'Error line= {}'.format(tb.tb_lineno) + '\n' + 'Error: {}'.format(sys.exc_info()[0]) + ' '+str(e)
            print(msg)
            self.conn.close()
        
 
        
        return

    #Naver뉴스 대댓글 Table 생성 함수
    def createNaverReReplyTable(self,dbname):
        self.connect()
        curs = self.conn.cursor()
        query = """use """+dbname
        curs.execute(query)
        self.conn.commit()
        #NaverNews라는 ID, URL, TITLE 등등을 포함하는 테이블을 생성
        query = """create table naver_rereplies(   
                                            article_id int not null, 
                                            reply_id int not null, 
                                            id int not null auto_increment primary key, 
                                            rerewriter varchar(512), 
                                            rereply_date varchar(50),
                                            rere text,
                                            rere_like int,
                                            rere_bad int,
                                            FOREIGN KEY(article_id) REFERENCES Naver_Articles(article_id) ON UPDATE CASCADE ON DELETE CASCADE,
                                            FOREIGN KEY(reply_id) REFERENCES Naver_Replies(reply_id) ON UPDATE CASCADE ON DELETE CASCADE
                                            )"""

        try:
            curs.execute(query)
            self.conn.commit()
            query = """ALTER TABLE naver_rereplies CHARACTER SET utf8 COLLATE utf8_general_ci;"""
            curs.execute(query)
            self.conn.commit()
            self.conn.close()
        except Exception as e :
            _, _, tb = sys.exc_info()  # tb -> traceback object
            msg = 'File name: ' + __file__ + '\n' + 'Error line= {}'.format(tb.tb_lineno) + '\n' + 'Error: {}'.format(sys.exc_info()[0]) + ' '+str(e)
            print(msg)      
            self.conn.close()
        
        return
    
    #네이버 댓글 DB입력
    def insertNaverReplyData(self, Article_ID, Reply_ID, Writer, ReplyDate ,Reply,ReRe_count,R_Like,R_Bad,R_Per_Like,R_Sentiment):
        try:
            self.connect()
            curs = self.conn.cursor()
            query = """insert into """ +self.dbname+ """.Naver_Replies(Article_ID, 
                                                    Writer, 
                                                    reply_date, 
                                                    Reply,
                                                    ReRe_count,
                                                    R_Like,
                                                    R_Bad,
                                                    R_Per_Like,
                                                    R_Sentiment) values (%s ,%s, %s, %s, %s, %s, %s, %s, %s)"""
            curs.execute(query, (Article_ID, Writer, ReplyDate, Reply, ReRe_count, R_Like, R_Bad, R_Per_Like, R_Sentiment))
            self.conn.commit()
            self.conn.close()
            lastIndex = curs.lastrowid
            return lastIndex
        except Exception as e :
            _, _, tb = sys.exc_info()  # tb -> traceback object
            msg = 'File name: ' + __file__ + '\n' + 'Error line= {}'.format(tb.tb_lineno) + '\n' + 'Error: {}'.format(sys.exc_info()[0]) + ' '+str(e)
            print(msg)  
            self.conn.close()
        

    #네이버 대댓글 DB입력
    def insertNaverReReplyData(self, Article_ID, Reply_ID, ReReply_ID, ReReWriter,ReReDate, ReRe, ReRe_Like, ReRe_Bad):
        try:
            self.connect()
            curs = self.conn.cursor()        
            query = """insert into """ +self.dbname+ """.Naver_ReReplies(   
                                                Article_ID,
                                                Reply_ID,
                                                ReReWriter,
                                                rereply_date,
                                                ReRe,
                                                ReRe_Like,
                                                ReRe_Bad) values (%s ,%s , %s, %s, %s, %s, %s)"""
            curs.execute(query, (Article_ID, Reply_ID, ReReWriter,ReReDate,ReRe, ReRe_Like, ReRe_Bad))
            self.conn.commit()
            self.conn.close()
        except Exception as e :
            _, _, tb = sys.exc_info()  # tb -> traceback object
            msg = 'File name: ' + __file__ + '\n' + 'Error line= {}'.format(tb.tb_lineno) + '\n' + 'Error: {}'.format(sys.exc_info()[0]) + ' '+str(e)
            print(msg)  
            self.conn.close()
        

    #네이버 기사 데이터 추가
    def insertNaverArticleData(self, data):
        try:
            self.connect()
            curs = self.conn.cursor()
            lastIndex = -1 
            query = """ insert into """ +self.dbname+ """.naver_articles (
            article_press, 
            article_type, 
            url, 
            article_title, 
            article_body, 
            article_date, 
            R_count, 
            male, 
            female, 
            tens, 
            twentys, 
            thirtys, 
            fortys, 
            fiftys,
            sixtys ) select * from ( select %s as a, %s as b, %s as c, %s as d, %s as e, %s as f,%s as g,%s as h, %s as i,%s as j, %s as k,%s as l,%s as m, %s as n,%s as o) as tmp
                        where not exists (SELECT 1 FROM """ +self.dbname+ """.naver_articles WHERE URL=%s) LIMIT 1;"""
            
            
            curs.execute(query, (data['article_press'], 
                                data['article_type'], 
                                data['url'], 
                                data['article_title'], 
                                data['article_body'], 
                                data['article_date'], 
                                data['R_count'], 
                                data['male'], 
                                data['female'], 
                                data['tens'], 
                                data['twentys'], 
                                data['thirtys'], 
                                data['fortys'], 
                                data['fiftys'], 
                                data['sixtys'], 
                                data['url']))
            lastIndex = curs.lastrowid
            print()
            print('LAST INDEX:=',lastIndex)
            print()
            self.conn.commit()
            self.conn.close()
            
            return lastIndex
        
        except Exception as e :
            _, _, tb = sys.exc_info()  # tb -> traceback object
            msg = 'File name: ' + __file__ + '\n' + 'Error line= {}'.format(tb.tb_lineno) + '\n' + 'Error: {}'.format(sys.exc_info()[0]) + ' '+str(e)
            print(msg)  
            self.conn.close()

        