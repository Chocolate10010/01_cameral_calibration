#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import cv2 as cv
import numpy as np
import glob
import xml.etree.ElementTree as ET
import argparse

class CameraCalibrator(object):
    def __init__(self, image_size: tuple):    
        # 初始化矩阵和数组
        try:
            self.image_size = image_size
            self.matrix = np.zeros((3, 3), dtype=np.float64)
            self.new_camera_matrix = np.zeros((3, 3), dtype=np.float64)
            self.dist = np.zeros((1, 5), dtype=np.float64)
            self.roi = np.zeros((4,), dtype=int)
        except Exception as e:
            print(f"初始化异常：{e}")
            raise

    def load_params(self, param_file:str='camera_params.xml'):
        if not os.path.exists(param_file):
            print("File {} does not exist.",format(param_file))
            exit(-1)
        tree = ET.parse(param_file)
        root = tree.getroot()
        mat_data = root.find('camera_matrix')
        matrix = dict()
        if mat_data:
            for data in mat_data.iter():
                matrix[data.tag] = data.text
            for i in range(9):
                self.matrix[i // 3][i % 3] = float(matrix['data{}'.format(i)])
        else:
            print('No element named camera_matrix was found in {}'.format(param_file))

        new_camera_matrix = dict()
        new_data = root.find('new_camera_matrix')
        if new_data:
            for data in new_data.iter():
                new_camera_matrix[data.tag] = data.text
            for i in range(9):
                self.new_camera_matrix[i // 3][i % 3] = float(new_camera_matrix['data{}'.format(i)])
        else:
            print('No element named new_camera_matrix was found in {}'.format(param_file))

        dist = dict()
        dist_data = root.find('camera_distortion')
        if dist_data:
            for data in dist_data.iter():
                dist[data.tag] = data.text
            for i in range(5):
                self.dist[0][i]= float(dist['data{}'.format(i)])
        else:
            print('No element named camera_distortion was found in {}'.format(param_file))

        roi = dict()
        roi_data = root.find('roi')
        if roi_data:
            for data in roi_data.iter():
                roi[data.tag] = data.text
            for i in range(4):
                self.roi[i] = int(roi['data{}'.format(i)])
        else:
            print('No element named roi was found in {}'.format(param_file))

    def save_params(self, save_path='camera_params.xml'):
        root = ET.Element('root')
        tree = ET.ElementTree(root)

        comment = ET.Element('about')
        comment.set('author', 'chenyr')
        comment.set('github', 'https://github.com/chenyr0021')
        root.append(comment)
        mat_node = ET.Element('camera_matrix')
        root.append(mat_node)
        for i, elem in enumerate(self.matrix.flatten()):
            child = ET.Element('data{}'.format(i))
            child.text = str(elem)
            mat_node.append(child)

        new_node = ET.Element('new_camera_matrix')
        root.append(new_node)
        for i, elem in enumerate(self.new_camera_matrix.flatten()):
            child = ET.Element('data{}'.format(i))
            child.text = str(elem)
            new_node.append(child)

        dist_node = ET.Element('camera_distortion')
        root.append(dist_node)
        for i, elem in enumerate(self.dist.flatten()):
            child = ET.Element('data{}'.format(i))
            child.text = str(elem)
            dist_node.append(child)

        roi_node = ET.Element('roi')
        root.append(roi_node)
        for i, elem in enumerate(self.roi):
            child = ET.Element('data{}'.format(i))
            child.text = str(elem)
            roi_node.append(child)

        tree.write(save_path, 'UTF-8')
        print("Saved params in {}.".format(save_path))


    def cal_real_corner(self, corner_height, corner_width, square_size):
        obj_corner = np.zeros([corner_height * corner_width, 3], np.float32)
    # 使用 np.mgrid 生成棋盘格角点的网格坐标
    # np.mgrid[0:corner_height, 0:corner_width] 生成一个 2D 网格
    # .T.reshape(-1, 2) 将网格坐标展平为 (corner_height * corner_width, 2) 的形状
        obj_corner[:, :2] = np.mgrid[0:corner_height, 0:corner_width].T.reshape(-1, 2)  # (w*h)*2
        return obj_corner * square_size

    def calibration(self, corner_height:int, corner_width:int, square_size:float):
        
        file_names = glob.glob('./chess/*.JPG') + glob.glob('./chess/*.jpg') + glob.glob('./chess/*.png')

        imgs_corner = []
        #中止条件
        criteria = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        print("中止条件：",criteria,"\n")
        
        objs_corner = []
        obj_corner = self.cal_real_corner(corner_height, corner_width, square_size)
        
        for file_name in file_names:        
            # 读取图像
            chess_img = cv.imread(file_name)
            # 核验图像尺寸
            assert (chess_img.shape[0] == self.image_size[1] and chess_img.shape[1] == self.image_size[0]), \
                "Image size does not match the given value {}.".format(self.image_size)
            # 取灰度
            gray = cv.cvtColor(chess_img, cv.COLOR_BGR2GRAY)
            # 直接调用cv库函数，找到棋盘格角点
            ret, img_corners = cv.findChessboardCorners(gray, (corner_height, corner_width))
               
            # append to img_corners
            if ret:
                # 绘制角点
                img_with_corners = cv.drawChessboardCorners(chess_img, (corner_height, corner_width), img_corners, ret)
        
                # 构造保存路径
                base_name = os.path.basename(file_name)  # 获取原始文件名
                save_path = os.path.join('./chess_with_corners', base_name.replace('.jpg', '_with_corners.jpg'))  # 修改文件名并保存到指定路径
                cv.imwrite(save_path, img_with_corners)
                
                # 添加到列表
                objs_corner.append(obj_corner)
                img_corners = cv.cornerSubPix(gray, img_corners, winSize=(square_size//2, square_size//2),
                                              zeroZone=(-1, -1), criteria=criteria)
                imgs_corner.append(img_corners)
            else:
                print("Fail to find corners in {}.".format(file_name))

        # calibration
        ret, self.matrix, self.dist, rvecs, tveces = cv.calibrateCamera(objs_corner, imgs_corner, self.image_size, None, None)
        self.new_camera_matrix, roi = cv.getOptimalNewCameraMatrix(self.matrix, self.dist, self.image_size, alpha=1)
        self.roi = np.array(roi)
        return ret


    def rectify_video(self, video_path:str):
        self.load_params()
        cap = cv.VideoCapture(video_path)
        if not cap.isOpened():
            print("Unable to open video.")
            return False
        fourcc = int(cap.get(cv.CAP_PROP_FOURCC))
        out_format = video_path.split('.')[-1]
        fps = int(cap.get(cv.CAP_PROP_FPS))
        out = cv.VideoWriter(filename='out.'+out_format, fourcc=0x00000021, fps=fps, frameSize=self.image_size)
        cv.namedWindow("origin", cv.WINDOW_NORMAL)
        cv.namedWindow("dst", cv.WINDOW_NORMAL)
        frame_count = int(cap.get(cv.CAP_PROP_FRAME_COUNT))
        for _ in range(frame_count):
            ret, img = cap.read()
            if ret:
                img = cv.resize(img, (self.image_size[0], self.image_size[1]))
                cv.imshow("origin", img)
                dst = self.rectify_image(img)
                cv.imshow("dst", dst)
                out.write(dst)
                cv.waitKey(1)
        cap.release()
        out.release()
        cv.destroyAllWindows()
        return True

    def rectify_camera(self, camera_id:int):
        self.load_params()
        cap = cv.VideoCapture(camera_id)
        if not cap.isOpened():
            print("Unable to open camera.")
            return False
        cv.namedWindow("origin", cv.WINDOW_NORMAL)
        cv.namedWindow("rectified", cv.WINDOW_NORMAL)
        while True:
            ret, img = cap.read()
            if ret:
                cv.imshow('origin', img)
                dst = self.rectify_image(img)
                cv.imshow('rectified', dst)
            if cv.waitKey(10) == 27:
                break
        cap.release()
        cv.destroyAllWindows()
        return True


    def rectify_image(self, img):
        if not isinstance(img, np.ndarray):
            AssertionError("Image type '{}' is not numpy.ndarray.".format(type(img)))
        dst = cv.undistort(img, self.matrix, self.dist, self.new_camera_matrix)
        x, y, w, h = self.roi
        dst = dst[y:y + h, x:x + w]
        dst = cv.resize(dst, (self.image_size[0], self.image_size[1]))
        return dst


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--image_size', type= str, help='width*height of image')
    parser.add_argument('--mode', type=str, choices=['calibrate', 'rectify'], help='to calibrate or rectify')
    parser.add_argument('--square', type=int, help='size of chessboard square, by mm')
    parser.add_argument('--corner', type=str, help='width*height of chessboard corner')
    parser.add_argument('--video_path', type=str, help='video to rectify')
    parser.add_argument('--camera_id', type=int, help='camera_id, default=0', default=0)
    args = parser.parse_args()
    calibrator = None
    try:
        image_size = tuple(int(i) for i in args.image_size.split('x'))
        if not isinstance(image_size, tuple) or len(image_size) != 2:
            raise ValueError("Invalid image_size. Expected a tuple of (width, height).")
        if not all(isinstance(dim, int) and dim > 0 for dim in image_size):
            raise ValueError("Invalid image_size. Width and height must be positive integers.")
    except:
        print("Invalid/Missing parameter: --image_size. Sample: \n\n"
              "    --image_size 1920x1080\n")
        exit(-1)
    else:
        print("--image_size 传入成功 \n")
        
    try:
        calibrator = CameraCalibrator(image_size)
    except:
        print("calibrator 实例化失败")
        exit(-1)
    else:
        print("calibrator 实例化成功 \n")

    if args.mode == 'calibrate':
        if not args.corner or not args.square:
            print("Missing parameters of corner/square. Using: \n\n"
                  "    --corner <width>x<height>\n\n"
                  "    --square <length of square>\n")
            exit(-1)
        corner = tuple(int(i) for i in args.corner.split('x'))
        if calibrator.calibration(corner[1], corner[0], args.square):
            calibrator.save_params()
        else:
            print("Calibration failed.")
    elif args.mode == 'rectify':
        if args.video_path:
            if os.path.exists(args.video_path):
                calibrator.rectify_video(args.video_path)
                print("Saving rectified video to ./out.{}".format(args.video_path.split('.')[-1]))
            else:
                print("File {} does not exist.".format(args.video_path))
        elif args.camera_id:
            print("Press ESC to quit.")
            calibrator.rectify_camera(args.camera_id)
    else:
        print("Invalid/Missing parameter '--mode'. Please choose from ['calibrate', 'rectify'].")
        exit(-1)