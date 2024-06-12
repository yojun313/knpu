import pandas
from googleapiclient.discovery import build
 
 
api_key = 'AIzaSyBP90vCq6xn3Og4N4EFqODcmti-F74rYXU'
video_id = '8KVoR0XhyYo'
 
comments = list()
api_obj = build('youtube', 'v3', developerKey=api_key)
request = api_obj.commentThreads().list(part='snippet,replies', videoId=video_id, maxResults=100)
 
while request:
    response = request.execute()
    for item in response['items']:
        try:
            comment = item['snippet']['topLevelComment']['snippet']
            comments.append([comment['textDisplay'], comment['authorDisplayName'], comment['publishedAt'], comment['likeCount']])
            print(item)
            try:
                if item['snippet']['totalReplyCount'] > 0:
                    for reply_item in item['replies']['comments']:
                        reply = reply_item['snippet']
                        comments.append([reply['textDisplay'], reply['authorDisplayName'], reply['publishedAt'], reply['likeCount']])
            except:
                pass
        except:
            pass
    if 'nextPageToken' in response:
        request = api_obj.commentThreads().list_next(request, response)
    else:
        break
print(len(comments))
df = pandas.DataFrame(comments)
df.to_csv('results.csv', header=['comment', 'author', 'date', 'num_likes'], index=None)