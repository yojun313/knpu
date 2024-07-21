from ToolModule import ToolModule
import os
import sys
import warnings
warnings.filterwarnings("ignore", category=UserWarning, message="Converting to PeriodArray/Index representation will drop timezone information")

class DATA_PROCESS(ToolModule):
    def __init__(self):
        super().__init__()

        pass

    def DataDivider(self, csv_path):
        csv_folder_path = os.path.dirname(csv_path)
        csv_name = os.path.basename(csv_path)
        data_path = os.path.join(csv_folder_path, csv_name.replace(".csv", "")) + '_분할 데이터'

        # noinspection PyBroadException
        try:
            os.mkdir(data_path)
        except:
            print('분할 데이터 폴더가 이미 존재합니다')
            sys.exit()

        print("\n File Reading...: ", end = '')
        csv_data = self.csvReader(csv_path)
        print("Complete")


        print("\n File Checking...: ", end = '')
        typeData = self.typeChecker(csv_name)
        crawlType = typeData['crawlType']
        fileType = typeData['fileType'].replace('.csv', '')
        print('Complete')


        print("\n File Processing...: ", end = ' ')
        csv_data = self.TimeSplitter(csv_data, crawlType, fileType)
        year_divided_group = csv_data.groupby('year')
        month_divided_group = csv_data.groupby('year_month')
        week_divided_group = csv_data.groupby('week')
        print('Complete')

        print("\n File Saving...: ", end = ' ')
        self.TimeSplitToCSV(1, year_divided_group, data_path)
        self.TimeSplitToCSV(2, month_divided_group, data_path)
        print("Complete")

    def main(self):
        print("\n1. 파일 분할(Year, Month, Week)\n2. URL 제외\n3. URL 포함\n4. 정렬 및 통계\n5. 댓글 공백 제거")
        while True:
            big_option = input("\n입력: ")
            if big_option in ["1", "2", "3", "4", "5"]:
                break
            else:
                print("다시 입력하세요")

        self.clear_screen()

        csv_path = self.file_ask("대상 csv 파일을 선택하세요")

        if int(big_option) == 1:
            self.DataDivider(csv_path)

object_obj = DATA_PROCESS()
object_obj.main()

