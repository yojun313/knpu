# first = True
# n = int(input())
# pm = 1
# cm = 1
# tmp = n
# tmp2 = 1
# for i in range(n):
#     print("a"*i, end = '')
#     if first:
#         print("○", end = '')
#         print(" "*(n-1), end = '')
#         print("●")
#         print()
#         print("a"*i, end = '')
#         print(" "*(n-1), end = '')
#         print("a"*i)
#         print()
#         frist = False
#     else:
#         print("a"*i, end = '')
#         print(" "*(tmp-2))
#         tmp -= 2
#         print("a"*i)
#         print()
#         tmp2 += 1
# #     if tmp2 == n//2:
# #         tmp2 = 1

# print("p        p")
# print("a        a")
# print("aa      aa")
# print("aaa    aaa")
# print("aaaa  aaaa")
# print("aaaaaaaaaa")

# import random

# seed_list = ["apple", "carrot", "beanstalk", "banna"]
# print(random.choice(seed_list))

n = int(input("n값을 입력하세요: "))
player_m = 7
comp_m = 3
line_list = []
all_list = []
tmp2 = [' ' for i in range(n+1)]
all_list.append(tmp2)
tmp = (n//2-1)*2 + 1

if n % 2 == 0:
    tmp = n
    for i in range(1, (n//2)+1):
        for j in range(i):
            line_list.append("a")
        for k in range(tmp-1):
            line_list.append(" ")
        for l in range(i):
            line_list.append("a")
        all_list.append(line_list)
        line_list = []
        tmp -= 2
else:
    tmp = n
    for i in range(1, (n//2)+2):
        for j in range(i):
            line_list.append("a")
        for k in range(tmp-1):
            line_list.append(" ")
        for l in range(i):
            line_list.append("a")
        all_list.append(line_list)
        line_list = []
        tmp -= 2

# if player_m == 0:
#     all_list[0][0] = '●'
# if comp_m == 0:
#     all_list[0][-1] = '○'

for i in range(n//2+1):

    # 겹칠 때
    if comp_m + player_m == n:
        if player_m == i and player_m < n//2 + 1:
            all_list[i][i] = '◑'
        elif i == n - player_m and player_m >= n//2 + 1:
            all_list[i][-i-1] = '◑'
        break

    if player_m == i and player_m < n//2 + 1:
        all_list[i][i] = '●'
    elif player_m >= n//2 + 1 and i == n - player_m:
        all_list[i][-i-1] = '●'

    if comp_m == i and comp_m < n//2 + 1:
        all_list[i][-i] = '○'
    elif i == n - comp_m and comp_m >= n//2 + 1:
        all_list[i][i] = '○'


for line in all_list:
    for i in line:
        print(i, end='')
    print()
"q         q"
"aq        a"
"aa       aa"
"aaa     aaa"
"aaaa   aaaa"
"aaaaa aaaaa"


# 플 1칸 또는 8칸 컴 1칸 또는 8칸
# 플 2칸 또는 7칸 컴 2칸 또는 7칸
# 플 3칸 또는 6칸
