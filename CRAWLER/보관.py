if self.weboption == 1:
    if print_type == "news":
        print_type = "기사"
        if signal == -1: # 날짜
            out_str = "\r"+"|| 진행: "+str(round((self.progress/(self.date_range+1))*100, 1))+"%"+ " | 경과: " +loadingtime+" | 날짜: "+self.trans_date+" | url: "+str(len(self.urlList))+" | "+print_type+": "+str(len(self.article_list)-1)+" | 댓글: "+str(len(self.reply_list)-1)+" | 대댓글: "+str(len(self.rereply_list)-1)+" ||"
            print(out_str, end = "")
        elif signal == 0: # url
            out_str = "\r"+"|| 진행: "+str(round((self.progress/(self.date_range+1))*100, 1))+"%"+  " | 경과: " +loadingtime+" | 날짜: "+self.trans_date+" | url: "+str(len(self.urlList))+" | "+print_type+": "+str(len(self.article_list)-1)+" | 댓글: "+str(len(self.reply_list)-1)+" | 대댓글: "+str(len(self.rereply_list)-1)+" ||"
            print(out_str, end = "")
        elif signal == 1: # 기사
            out_str = "\r"+"|| 진행: "+str(round((self.progress/(self.date_range+1))*100, 1))+"%"+  " | 경과: " +loadingtime+" | 날짜: "+self.trans_date+" | url: "+str(len(self.urlList))+" | "+print_type+": "+str(len(self.article_list)-1)+" | 댓글: "+str(len(self.reply_list)-1)+" | 대댓글: "+str(len(self.rereply_list)-1)+" ||"
            print(out_str, end = "")
        elif signal == 2: # 댓글
            out_str = "\r"+"|| 진행: "+str(round((self.progress/(self.date_range+1))*100, 1))+"%"+  " | 경과: " +loadingtime+" | 날짜: "+self.trans_date+" | url: "+str(len(self.urlList))+" | "+print_type+": "+str(len(self.article_list)-1)+" | 댓글: "+str(len(self.reply_list)-1)+" | 대댓글: "+str(len(self.rereply_list)-1)+" ||"
            print(out_str, end = "")
        else: # 대댓글
            out_str = "\r"+"|| 진행: "+str(round((self.progress/(self.date_range+1))*100, 1))+"%"+  " | 경과: " +loadingtime+" | 날짜: "+self.trans_date+" | url: "+str(len(self.urlList))+" | "+print_type+": "+str(len(self.article_list)-1)+" | 댓글: "+str(len(self.reply_list)-1)+" | 대댓글: "+str(len(self.rereply_list)-1)+" ||"
            print(out_str, end = "")
    
    elif print_type == "blog":
        print_type = "블로그"
        if signal == -1: # 날짜
            out_str = "\r"+"|| 진행: "+str(round((self.progress/(self.date_range+1))*100, 1))+"%"+  " | 경과: " +loadingtime+" | 날짜: "+self.trans_date+" | url: "+str(len(self.urlList))+" | "+print_type+": "+str(len(self.article_list)-1)+" | 댓글: "+str(len(self.reply_list)-1)+" ||"
            print(out_str, end = "")
        elif signal == 0: # url
            out_str = "\r"+"|| 진행: "+str(round((self.progress/(self.date_range+1))*100, 1))+"%"+  " | 경과: " +loadingtime+" | 날짜: "+self.trans_date+" | url: "+str(len(self.urlList))+" | "+print_type+": "+str(len(self.article_list)-1)+" | 댓글: "+str(len(self.reply_list)-1)+" ||"
            print(out_str, end = "")
        elif signal == 1: # 블로그
            out_str = "\r"+"|| 진행: "+str(round((self.progress/(self.date_range+1))*100, 1))+"%"+  " | 경과: " +loadingtime+" | 날짜: "+self.trans_date+" | url: "+str(len(self.urlList))+" | "+print_type+": "+str(len(self.article_list)-1)+" | 댓글: "+str(len(self.reply_list)-1)+" ||"
            print(out_str, end = "")
        else: # 댓글
            out_str = "\r"+"|| 진행: "+str(round((self.progress/(self.date_range+1))*100, 1))+"%"+  " | 경과: " +loadingtime+" | 날짜: "+self.trans_date+" | url: "+str(len(self.urlList))+" | "+print_type+": "+str(len(self.article_list)-1)+" | 댓글: "+str(len(self.reply_list)-1)+" ||"
            print(out_str, end = "")
    
    elif print_type == "youtube":
        print_type = "영상"
        
        if signal == -1: # 날짜
            out_str = "\r"+"|| 진행: "+str(round((self.progress/(self.date_range+1))*100, 1))+"%"+  " | 경과: " +loadingtime+" | 날짜: "+self.trans_date+" | url: "+str(len(self.urlList))+" | "+print_type+": "+str(len(self.info_list)-1)+" | 댓글: "+str(len(self.reply_list)-1)+" ||"
            print(out_str, end = "")
        elif signal == 0: # url
            out_str = "\r"+"|| 진행: "+str(round((self.progress/(self.date_range+1))*100, 1))+"%"+  " | 경과: " +loadingtime+" | 날짜: "+self.trans_date+" | url: "+str(len(self.urlList))+" | "+print_type+": "+str(len(self.info_list)-1)+" | 댓글: "+str(len(self.reply_list)-1)+" ||"
            print(out_str, end = "")
        elif signal == 1: # 블로그
            out_str = "\r"+"|| 진행: "+str(round((self.progress/(self.date_range+1))*100, 1))+"%"+  " | 경과: " +loadingtime+" | 날짜: "+self.trans_date+" | url: "+str(len(self.urlList))+" | "+print_type+": "+str(len(self.info_list)-1)+" | 댓글: "+str(len(self.reply_list)-1)+" ||"
            print(out_str, end = "")
        else: # 댓글
            out_str = "\r"+"|| 진행: "+str(round((self.progress/(self.date_range+1))*100, 1))+"%"+  " | 경과: " +loadingtime+" | 날짜: "+self.trans_date+" | url: "+str(len(self.urlList))+" | "+print_type+": "+str(len(self.info_list)-1)+" | 댓글: "+str(len(self.reply_list)-1)+" ||"
            print(out_str, end = "")