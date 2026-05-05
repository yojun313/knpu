import pandas as pd
import os


def makeCSV(tablePath, tableName, columns):
    df = pd.DataFrame(columns=columns)
    file_path = os.path.join(tablePath, tableName + ".csv")
    df.to_csv(file_path, index=False, encoding="utf-8-sig")


def addToCSV(tablePath, tableName, data_list, columns):
    df_new = pd.DataFrame(data_list, columns=columns)
    file_path = os.path.join(tablePath, f"{tableName}.csv")

    # if not os.path.exists(file_path):
    #     self.running = False
    #     print('\rStopped by MANAGER', end='')

    #     log = open(os.path.join(self.crawllog_path,
    #                 self.DBname + '_log.txt'), 'a')
    #     log.write(
    #         f"\n\nDB Check --> {datetime.fromtimestamp(self.startTime).strftime('%Y%m/%d %H:%M')}에 중단됨")
    #     log.close()
    #     self.sendPushOver(self.halt_msg, user_key=self.pushoverKey)

    #     self.localDBRemover()
    #     sys.exit()

    write_header = not os.path.exists(file_path)
    df_new.to_csv(file_path, mode="a", header=write_header, index=False)
