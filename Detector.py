import cv2
import numpy as np


class DetectorShape:
    """
    形状 / 图像算子集合。

    注意（2026.10.2 数据流引擎之后）：这里的检测函数只负责"算"。
    它们顺手画在传入数组上的绿线、红圆只是副作用，会被引擎丢掉；
    真正给用户看的叠加绘制统一由 NodeRegistry.py 的 _draw_line() / _draw_circle()
    在显示层完成，这样检测结果永远不会污染下游节点的输入图像。
    """

    # 注：灰度化（原来的 gray_bgr）2026.10.3 已搬到 ProcessOps.to_gray()——
    #     本文件只放检测类算法，处理类（灰度等）统一归 ProcessOps.py。

    def line_detector(self, img, rho = 1.0, theta = np.pi / 180,
                      threshold = 100, min_line_length = 100.0,
                      max_line_gap = 10.0, canny_low = 50,
                      canny_high = 150, aperture = 3,
                      roi_offset_x=0, roi_offset_y=0):
        """
        检测图像中的直线段，并在原图上绘制绿色线段。

        参数:
            img: 输入图像（BGR格式）
            rho: 距离分辨率（像素）
            theta: 角度分辨率（弧度）
            threshold: 累加器阈值，值越小检测到的线段越多
            minLineLength: 最小线段长度，短于此值的线段被丢弃
            maxLineGap: 同一线段上允许的最大间断间隔（像素）
            canny_low: Canny边缘检测的低阈值
            canny_high: Canny边缘检测的高阈值
            aperture: Sobel算子的大小
            roi_offset_x: 直线检测区域的 x轴偏移量
            roi_offset_y: 直线检测区域的 y轴偏移量

        返回:
            (绘制了线段的图像, 直线数据列表)
            直线数据是 (x1, y1, x2, y2)，坐标已经加上偏移量、换回主图坐标
        """
        if len(img.shape) == 2:
            gray = img
        else:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        edges = cv2.Canny(gray, canny_low, canny_high, apertureSize=aperture)
        lines = cv2.HoughLinesP(edges, rho=rho, theta=theta, threshold=threshold,
                                minLineLength=min_line_length, maxLineGap=max_line_gap)
        line_data = []
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                cv2.line(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                # 把相对于子图的坐标，加上偏移量，转化为主图的真实坐标
                x1 += roi_offset_x
                y1 += roi_offset_y
                x2 += roi_offset_x
                y2 += roi_offset_y
                line_data.append((x1, y1, x2, y2))
        return img, line_data

    def circle_detector(self, img, method = cv2.HOUGH_GRADIENT, dp = 1.0,
                        min_dist = 150.0, param1 = 100.0, param2 = 80.0,
                        min_radius = 20, max_radius = 0,
                        roi_offset_x=0, roi_offset_y=0):
        """
        检测图像中的圆形，并在原图上绘制红色圆。

        参数:
            img: 输入图像（BGR格式）
            method: 检测方法，目前仅支持cv2.HOUGH_GRADIENT
            dp: 累加器分辨率与图像分辨率的反比（dp=1时分辨率相同）
            minDist: 圆心之间的最小距离，避免检测到相邻的圆
            param1: Canny边缘检测的高阈值（低阈值为它的一半）
            param2: 圆心检测的累加器阈值，越小检测到的圆越多（可能包含假圆）
            minRadius: 最小圆半径
            maxRadius: 最大圆半径（0表示无限制）
            roi_offset_x: 圆检测区域的 x轴偏移量
            roi_offset_y: 圆检测区域的 y轴偏移量

        返回:
            (绘制了圆形的图像, 圆数据列表)
            圆数据是 (cx, cy, r)，坐标已经加上偏移量、换回主图坐标
        """
        if len(img.shape) == 2:
            gray = img
        else:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        circles = cv2.HoughCircles(gray, method, dp, min_dist, param1=param1,
                                       param2=param2, minRadius=min_radius,
                                       maxRadius=max_radius)
        circle_data = []
        if circles is not None:
            circles = np.round(circles[0, :]).astype(int)
            for (x, y, r) in circles:
                cv2.circle(img, (x, y), r, (0, 0, 255), 2)  # 红色圆
                cv2.circle(img, (x, y), 2, (0, 0, 255), 3)  # 圆心
                circle_data.append((x + roi_offset_x, y + roi_offset_y, r))
        return img, circle_data


def make_test_image():
    """造一张带矩形、圆和一条长横线的测试图，供单独运行本文件 / 其它自检使用"""
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.rectangle(img, (100, 100), (500, 400), (255, 255, 255), 2)
    cv2.circle(img, (300, 250), 80, (255, 255, 255), 2)
    cv2.line(img, (120, 430), (520, 430), (255, 255, 255), 3)
    return img


def main():
    """
    独立测试：优先读 image/lena.png，读不到就自己造一张
    （工程里没有 image 目录时也能正常跑，不会再直接崩）
    """
    detector = DetectorShape()

    img = cv2.imread('image/lena.png')
    if img is None:
        print("没找到 image/lena.png，改用自动生成的测试图")
        img = make_test_image()


    canvas, line_data = detector.line_detector(img)
    canvas, circle_data = detector.circle_detector(img)
    print("检测到直线：", line_data)
    print("检测到圆：", circle_data)

    cv2.imshow('img', canvas)
    cv2.waitKey(0)


if __name__ == '__main__':
    main()
