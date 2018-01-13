# -*- coding: utf-8 -*-

"""
# === 思路 ===
# 核心：每次落稳之后截图，根据截图算出棋子的坐标和下一个块顶面的中点坐标，
#      根据两个点的距离乘以一个时间系数获得长按的时间
# 识别棋子：靠棋子的颜色来识别位置，通过截图发现最下面一行大概是一条
           直线，就从上往下一行一行遍历，比较颜色（颜色用了一个区间来比较）
           找到最下面的那一行的所有点，然后求个中点，求好之后再让 Y 轴坐标
           减小棋子底盘的一半高度从而得到中心点的坐标
# 识别棋盘：靠底色和方块的色差来做，从分数之下的位置开始，一行一行扫描，
           由于圆形的块最顶上是一条线，方形的上面大概是一个点，所以就
           用类似识别棋子的做法多识别了几个点求中点，这时候得到了块中点的 X
           轴坐标，这时候假设现在棋子在当前块的中心，根据一个通过截图获取的
           固定的角度来推出中点的 Y 坐标
# 最后：根据两点的坐标算距离乘以系数来获取长按时间（似乎可以直接用 X 轴距离）
"""
import os
import shutil
import time
import math
import random
import json
import cv2
import numpy as np
from PIL import Image, ImageDraw
import wda
import sys



'''
with open('config.json', 'r') as f:
    config = json.load(f)


# Magic Number，不设置可能无法正常执行，请根据具体截图从上到下按需设置
under_game_score_y = config['under_game_score_y']
# 长按的时间系数，请自己根据实际情况调节
press_coefficient = config['press_coefficient']
# 二分之一的棋子底座高度，可能要调节
piece_base_height_1_2 = config['piece_base_height_1_2']
# 棋子的宽度，比截图中量到的稍微大一点比较安全，可能要调节
piece_body_width = config['piece_body_width']
time_coefficient = config['press_coefficient']
head_diameter = config.get('head_diameter', 60)

    
# 模拟按压的起始点坐标，需要自动重复游戏请设置成“再来一局”的坐标
swipe = config.get('swipe', {
    "x1": 320,
    "y1": 410,
    "x2": 320,
    "y2": 410
    })
'''
under_game_score_y = 250
piece_base_height_1_2=13
piece_body_width=47


c = wda.Client()
s = c.session()


screenshot_backup_dir = 'screenshot_backups/'
if not os.path.isdir(screenshot_backup_dir):
    os.mkdir(screenshot_backup_dir)


def pull_screenshot():
    c.screenshot('1.png')


def jump(distance,im,target):
    #press_time = distance * time_coefficient * random.uniform(0.9999, 1.0001) / 1000
    #scale = 0.945 * 2 / head_diameter
    #actual_distance = distance * scale * (math.sqrt(6) / 2)
    #press_time = (-945 + math.sqrt(945 ** 2 + 4 * 105 * 36 * actual_distance)) / (2 * 105) * 1000
    
    #distanceX = abs(board_x-piece_x) #起点到目标的水平距离
    press_time=0.0
    shortEdge = min(im.size) #屏幕宽度
    #jumpPercent = distance/shortEdge #跳跃百分比
    jumpFullWidth = 1700 #跳过整个宽度 需要按压的毫秒数
    press_time =max(round(jumpFullWidth*distance/shortEdge),200.0)/1000 #按压时长
    print('press time: {}'.format(press_time),distance,shortEdge)
    if random.uniform(0,1)>0.2 :
        press_time =press_time+random.uniform(-1,1)*(target-20)/1500
        print('press real time: {}'.format(press_time),distance,shortEdge)
    
    s.tap_hold(200*random.uniform(0.98, 1.02), 200*random.uniform(0.98, 1.02), press_time)  

def backup_screenshot(ts):
    """
    为了方便失败的时候 debug
    """
    if not os.path.isdir(screenshot_backup_dir):
        os.mkdir(screenshot_backup_dir)
    shutil.copy('1.png', '{}{}.png'.format(screenshot_backup_dir, ts))


def save_debug_creenshot(ts, im, piece_x, piece_y, board_x, board_y):
    draw = ImageDraw.Draw(im)
    # 对debug图片加上详细的注释
    draw.line((piece_x, piece_y) + (board_x, board_y), fill=2, width=3)
    draw.line((piece_x, 0, piece_x, im.size[1]), fill=(255, 0, 0))
    draw.line((0, piece_y, im.size[0], piece_y), fill=(255, 0, 0))
    draw.line((board_x, 0, board_x, im.size[1]), fill=(0, 0, 255))
    draw.line((0, board_y, im.size[0], board_y), fill=(0, 0, 255))
    draw.ellipse(
        (piece_x - 10, piece_y - 10, piece_x + 10, piece_y + 10),
        fill=(255, 0, 0))
    draw.ellipse(
        (board_x - 10, board_y - 10, board_x + 10, board_y + 10),
        fill=(0, 0, 255))
    del draw
    im.save('{}{}_d.png'.format(screenshot_backup_dir, ts))


def set_button_position(im):
    """
    将swipe设置为 `再来一局` 按钮的位置
    """
    global swipe_x1, swipe_y1, swipe_x2, swipe_y2
    w, h = im.size
    left = w / 2
    top = 1003 * (h / 1280.0) + 10
    swipe_x1, swipe_y1, swipe_x2, swipe_y2 = left, top, left, top


def find_piece_and_board(im,num_ex,ts):
    w, h = im.size
    piece_body_width2=int(piece_body_width*w/750)
    print("size: {}, {}".format(w, h))
    draw = ImageDraw.Draw(im)
    piece_x_sum = piece_x_c = piece_y_max = 0
    board_x = board_y = 0
    scan_x_border = int(w / 8)  # 扫描棋子时的左右边界
    scan_start_y = 0  # 扫描的起始 y 坐标
    im_pixel = im.load()
    im2 = im
    im = np.array(im2)
    
    # 以 50px 步长，尝试探测 scan_start_y
    for i in range(under_game_score_y+100, h, 50):
        last_pixel = im_pixel[0, i]
        for j in range(1, w):
            pixel = im_pixel[j, i]

            # 不是纯色的线，则记录scan_start_y的值，准备跳出循环
            if pixel != last_pixel:
                scan_start_y = i - 50
                break

        if scan_start_y:
            break

    print("scan_start_y: ", scan_start_y)

    # 从 scan_start_y 开始往下扫描，棋子应位于屏幕上半部分，这里暂定不超过 2/3
    for i in range(scan_start_y, int(h * 2 / 3)):
        # 横坐标方面也减少了一部分扫描开销
        for j in range(scan_x_border, w - scan_x_border):
            pixel = im_pixel[j, i]
            # 根据棋子的最低行的颜色判断，找最后一行那些点的平均值，这个颜
            # 色这样应该 OK，暂时不提出来
            if (50 < pixel[0] < 60) \
                    and (53 < pixel[1] < 63) \
                    and (95 < pixel[2] < 110):
                piece_x_sum += j
                piece_x_c += 1
                piece_y_max = max(i, piece_y_max)

    if not all((piece_x_sum, piece_x_c)):
        return 0, 0, 0, 0,0
    piece_x = piece_x_sum / piece_x_c
    piece_y = piece_y_max - piece_base_height_1_2  # 上移棋子底盘高度的一半
    if piece_x < w/2:
            start_idx = piece_x+int(piece_body_width2+1)/2
            end_idx = w
            idx = -1
    else:
            start_idx = 0
            end_idx = piece_x-int(piece_body_width2+1)/2
            idx = 0

    # find board location
    im = im[(under_game_score_y+100):h, start_idx:end_idx]
    h, w, c = im.shape
    im = cv2.bilateralFilter(im, 11, 17, 17)
    edged = cv2.Canny(im, 30, 100)
    for i in range(0, h):
            if any(edged[i, :]):
                indices = np.where(edged[i, :] != 0)[0]
                board_x = int(round((indices[0]+indices[-1])/2)) + start_idx
                break
    width = -1
    for j in range(i+2, i+274, 5):
        indices = np.where(edged[j, :] != 0)[0] + start_idx
        if not len(indices):
            continue
        if abs((indices[0] + indices[-1])/2 - board_x) <= 5: ##
            if abs(indices[idx] - board_x) <= width: ##
                board_y = j+under_game_score_y+100
                break
            else:
                width = abs(indices[idx] - board_x)
        else:
            board_y = j+under_game_score_y+100
            break
    #board_y = piece_y - abs(board_x - piece_x) * math.sqrt(3) / 3
    target=(board_y-i-under_game_score_y-100)*piece_body_width/piece_body_width2
    return piece_x, piece_y, board_x, board_y,target

'''
    board_x_sum = 0
    board_x_sum_old=0
    board_x_c = 0
    num=1
    for i in range(int(h / 3), int(h * 2 / 3)):
        last_pixel = im_pixel[10, int(h / 3)]
        if board_x:
            #del draw
            #im.save('{}{}_t.png'.format(screenshot_backup_dir, ts))
            break

        
        for j in range(w):
            pixel = im_pixel[j, i]
            # 修掉脑袋比下一个小格子还高的情况的 bug
            if abs(j - piece_x) < piece_body_width:
                continue

            # 修掉圆顶的时候一条线导致的小 bug，这个颜色判断应该 OK，暂时不提出来
            #if abs(pixel[0] - last_pixel[0]) >=1:
            #if abs(pixel[1] - last_pixel[1]) >=1:
            #if abs(pixel[2] - last_pixel[2]) >=1:
            if (abs(pixel[0] - last_pixel[0])>4 or abs(pixel[1] - last_pixel[1])>4 or abs(pixel[2] - last_pixel[2]) > 4 ):
                 if not (abs(pixel[0] - last_pixel[0])<3 or abs(pixel[1] - last_pixel[1])<3 or abs(pixel[2] - last_pixel[2]) <3 ):
                            #print debug
                            if debug>0:
                                draw.ellipse((j-3, i-3, j, i),fill=(128, 128, 128))
                                print (abs(pixel[0] - last_pixel[0]),abs(pixel[1] - last_pixel[1]),abs(pixel[2] - last_pixel[2]),j,i)
                            board_x_sum += j
                            board_x_c += 1

        if board_x_sum!=board_x_sum_old:
            if board_x_c>50:
               board_x_c=0
               board_x_sum=0
               continue
            if num<num_ex:
                num+=1
                board_x_sum_old=board_x_sum
            else:
                board_x = board_x_sum / board_x_c
                

    # 按实际的角度来算，找到接近下一个 board 中心的坐标 这里的角度应该
    # 是 30°,值应该是 tan 30°, math.sqrt(3) / 3
    board_y = piece_y - abs(board_x - piece_x) * math.sqrt(3) / 3

    if not all((board_x, board_y)):
        return 0, 0, 0, 0

    return piece_x, piece_y, board_x, board_y
'''
def find_piece_and_board2(im,num_ex,ts):
    w, h = im.size
    
    print("size: {}, {}".format(w, h))
    draw = ImageDraw.Draw(im)
    piece_x_sum = piece_x_c = piece_y_max = 0
    board_x = board_y = 0
    scan_x_border = int(w / 8)  # 扫描棋子时的左右边界
    scan_start_y = 0  # 扫描的起始 y 坐标
    im_pixel = im.load()
   
       # 以 50px 步长，尝试探测 scan_start_y
    for i in range(under_game_score_y, h, 50):
        last_pixel = im_pixel[0, i]
        for j in range(1, w):
            pixel = im_pixel[j, i]

            # 不是纯色的线，则记录scan_start_y的值，准备跳出循环
            if pixel != last_pixel:
                scan_start_y = i - 50
                break

        if scan_start_y:
            break

    print("scan_start_y: ", scan_start_y)

    # 从 scan_start_y 开始往下扫描，棋子应位于屏幕上半部分，这里暂定不超过 2/3
    for i in range(scan_start_y, int(h * 2 / 3)):
        # 横坐标方面也减少了一部分扫描开销
        for j in range(scan_x_border, w - scan_x_border):
            pixel = im_pixel[j, i]
            # 根据棋子的最低行的颜色判断，找最后一行那些点的平均值，这个颜
            # 色这样应该 OK，暂时不提出来
            if (50 < pixel[0] < 60) \
                    and (53 < pixel[1] < 63) \
                    and (95 < pixel[2] < 110):
                piece_x_sum += j
                piece_x_c += 1
                piece_y_max = max(i, piece_y_max)

    if not all((piece_x_sum, piece_x_c)):
        return 0, 0, 0, 0
 
    piece_x = piece_x_sum / piece_x_c
    piece_y = piece_y_max - piece_base_height_1_2  # 上移棋子底盘高度的一半




    board_x_sum = 0
    board_x_sum_old=0
    board_x_c = 0
    num=1
    for i in range(int(h / 3), int(h * 2 / 3)):
        last_pixel = im_pixel[10, int(h / 3)]
        if board_x:
        #del draw
        #im.save('{}{}_t.png'.format(screenshot_backup_dir, ts))
            break
        
        
        for j in range(w):
            pixel = im_pixel[j, i]
            # 修掉脑袋比下一个小格子还高的情况的 bug
            if abs(j - piece_x) < piece_body_width:
                continue
            
            # 修掉圆顶的时候一条线导致的小 bug，这个颜色判断应该 OK，暂时不提出来
            #if abs(pixel[0] - last_pixel[0]) >=1:
            #if abs(pixel[1] - last_pixel[1]) >=1:
            #if abs(pixel[2] - last_pixel[2]) >=1:
            if (abs(pixel[0] - last_pixel[0])>4 or abs(pixel[1] - last_pixel[1])>4 or abs(pixel[2] - last_pixel[2]) > 4 ):
                if not (abs(pixel[0] - last_pixel[0])<3 or abs(pixel[1] - last_pixel[1])<3 or abs(pixel[2] - last_pixel[2]) <3 ):
            #print debug
                    draw.ellipse((j-3, i-3, j, i),fill=(128, 128, 128))
                    if debug>1:
                        
                        print (abs(pixel[0] - last_pixel[0]),abs(pixel[1] - last_pixel[1]),abs(pixel[2] - last_pixel[2]),j,i)
                board_x_sum += j
                board_x_c += 1
            
        if board_x_sum!=board_x_sum_old:
            if board_x_c>300:
                board_x_c=0
                board_x_sum=0
                continue
            if num<num_ex:
                num+=1
                board_x_sum_old=board_x_sum
            else:
                    board_x = board_x_sum / board_x_c
    
    
    # 按实际的角度来算，找到接近下一个 board 中心的坐标 这里的角度应该
    # 是 30°,值应该是 tan 30°, math.sqrt(3) / 3
    board_y = piece_y - abs(board_x - piece_x) * math.sqrt(3) / 3
    
    if not all((board_x, board_y)):
        return 0, 0, 0, 0
    
    return piece_x, piece_y, board_x, board_y



def main(argv):
    if len(argv)>=2 :
        im = Image.open("./1.png")
            
            # 获取棋子和 board 的位置
        global debug
        debug=10
        ts = int(time.time())
        piece_x, piece_y, board_x, board_y,target = find_piece_and_board(im,int(argv[1]),ts)
        
        print(ts, piece_x, piece_y, board_x, board_y)
        save_debug_creenshot(ts, im, piece_x, piece_y, board_x, board_y)
        return
    shutil.rmtree("screenshot_backups")
    while True:
        pull_screenshot()
        im = Image.open("./1.png")
        
        debug=1
        # 获取棋子和 board 的位置
        ts = int(time.time())
        piece_x, piece_y, board_x, board_y,target = find_piece_and_board(im,5,ts)
        
        print("M1",ts, piece_x, piece_y, board_x, board_y,target)
        #piece_x2, piece_y2, board_x2, board_y2 = find_piece_and_board2(im,3,ts)
        
        #print("M2",ts, piece_x2, piece_y2, board_x2, board_y2)


        if piece_x == 0:
            return
        
        #set_button_position(im)
        distance = math.sqrt((board_x - piece_x) ** 2 + (board_y - piece_y) ** 2)*math.sqrt(3) /2
            #if abs(board_x-board_x2)<4 :
            #      board_x=round(board_x2+board_x)/2
        #distance=abs(board_x-piece_x)
        #print("jump",ts, piece_x, piece_y, board_x, board_y)
        jump(distance,im,target)
        backup_screenshot(ts)
        save_debug_creenshot(ts, im, piece_x, piece_y, board_x, board_y)
        
        # 为了保证截图的时候应落稳了，多延迟一会儿，随机值防 ban
        time.sleep(random.uniform(1, 1.6))


if __name__ == '__main__':
    main(sys.argv)
