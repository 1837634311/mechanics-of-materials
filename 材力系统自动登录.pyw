# 需要安装的第三方库
import pyautogui

import base64
import json
import os
import subprocess
import time
import requests


def check_process(process_name):
    """检查进程是否存在"""
    try:
        result = subprocess.run(['tasklist', '/FI', f'IMAGENAME eq {process_name}'],
                                capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        exists = process_name in result.stdout
        print(f"进程 {process_name} {'存在' if exists else '不存在'}")
        return exists
    except Exception as e:
        print(f"检查进程 {process_name} 失败: {e}")
        return False


def kill_process(process_name, force=True, wait_time=0.3):
    """终止进程"""
    try:
        cmd = ['taskkill', '/IM', process_name]
        if force:
            cmd.append('/F')
        subprocess.run(cmd, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        print(f"已终止进程: {process_name}")
        time.sleep(wait_time)
        return True
    except Exception as e:
        print(f"终止进程 {process_name} 失败: {e}")
        return False


def start_process(app_path, wait_time=0.1, background=True):
    """启动进程"""
    try:
        if background:
            subprocess.Popen(app_path, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            os.startfile(app_path)
        print(f"已启动 {os.path.basename(app_path)}")
        time.sleep(wait_time)
        return True
    except Exception as e:
        print(f"启动 {app_path} 失败: {e}")
        return False


def wait_for_color_change(target_coords, target_color, timeout=10, interval=0.1):
    """检测颜色变化，用来判断程序是否响应"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        current_color = pyautogui.pixel(*target_coords)
        if current_color == target_color:
            return True
        time.sleep(interval)
    print("颜色未在规定时间内匹配，超时！")
    return False


def capture_to_base64(region, temp_file="temp_captcha.png"):
    """截图并转换为base64编码"""
    try:
        screenshot = pyautogui.screenshot(region=region)
        screenshot.save(temp_file)
        with open(temp_file, "rb") as f:
            img_str = base64.b64encode(f.read()).decode('utf-8')
        os.remove(temp_file)
        return img_str
    except Exception as e:
        print(f"截图失败: {e}")
        return None


def recognize_captcha(base64_img, ocr_url="http://127.0.0.1:1224/api/ocr", language="models/config_chinese.txt"):
    """调用 ocr 识别验证码"""
    headers = {"Content-Type": "application/json"}
    data = {
        "base64": base64_img,
        "options": {"ocr.language": language, "data.format": "text"}
    }
    try:
        response = requests.post(ocr_url, data=json.dumps(data), headers=headers, timeout=5)
        response.raise_for_status()
        res_dict = response.json()
        if res_dict["code"] == 100:
            text = "".join(res_dict["data"].split())
            print(f"OCR 识别结果: '{text}'")
            return text
        else:
            print(f"OCR 识别失败: {res_dict['data']}")
            return None
    except Exception as e:
        print(f"OCR 请求失败: {e}")
        return None


def click_and_type(x, y, text=None, interval=0):
    """点击输入框并输入文本"""
    pyautogui.click(x, y)
    if text:
        pyautogui.typewrite(text, interval=interval)


def fill_credentials(coords, username=None, password=None):
    """填写用户名和密码"""
    if username:
        click_and_type(*coords["username"], username)
    if password:
        click_and_type(*coords["password"], password)


def fill_captcha(coords, captcha):
    """填写验证码"""
    click_and_type(*coords["captcha_input"], captcha)


def type_captcha_and_confirm(coords, captcha_region):
    """识别验证码并填写"""
    captcha_base64 = capture_to_base64(captcha_region)
    if captcha_base64:
        captcha_text = recognize_captcha(captcha_base64)
        if captcha_text:
            fill_captcha(coords, captcha_text)
            click_and_type(*coords["confirm"])
            print("已自动填写验证码并点击确认")
        else:
            print("验证码识别失败，请手动输入")
    else:
        print("验证码截图失败，请手动输入")


def wait_for_ocr(ocr_process, max_wait_ocr=10):
    """等待 umi-ocr 启动"""
    for _ in range(max_wait_ocr):
        if check_process(ocr_process):
            return True
        time.sleep(0.1)
    print("umi-ocr 未在规定时间内启动")
    return False


def main(config):
    """自动登录函数"""
    app_path = config["app_path"]
    process_name = config["process_name"]
    ocr_path = config["ocr_path"]
    coords = config["coords"]
    captcha_region = config["captcha_region"]
    username = config["username"]
    password = config["password"]
    max_wait_ocr = config.get("max_wait_ocr", 10)
    target_color = config.get("target_color", (255, 255, 255))
    target_pos_2 = config["target_pos_2"]
    target_color_2 = config["target_color_2"]
    target_color_3 = config["target_color_3"]
    ocr_process = config.get("ocr_process", "Umi-OCR.exe")

    # 检查并启动 umi-ocr
    ocr_running = check_process(ocr_process)
    if not ocr_running:
        start_process(ocr_path)
        print("等待 umi-ocr 启动...")
        if not wait_for_ocr(ocr_process, max_wait_ocr):
            print("umi-ocr 启动失败，脚本终止。")
            return

    # 终止目标进程并启动应用
    if check_process(process_name):
        kill_process(process_name)
    start_process(app_path, wait_time=0)

    # 检测窗口并填写凭据
    if wait_for_color_change(coords["username"], target_color) and wait_for_color_change(target_pos_2, target_color_2):
        fill_credentials(coords, username=username, password=password)
        type_captcha_and_confirm(coords, captcha_region)
    else:
        print("登录窗口未检测到，脚本终止。")
        return

    # 检查验证码是否需要重试
    attempts = 0
    while attempts < 3:
        if not wait_for_color_change(coords["window_check"], target_color_3, timeout=3):
            break
        print("检测到验证码错误，尝试重新识别")
        click_and_type(*coords["captcha_input"])
        pyautogui.press('backspace')
        type_captcha_and_confirm(coords, captcha_region)
        attempts += 1
    if attempts >= 3:
        print("验证码识别失败多次，请手动输入")


if __name__ == "__main__":
    login_config = {
        "app_path": "学生系统.lnk",
        "process_name": "studenthow.exe",
        "ocr_path": "Umi-OCR.exe",
        "ocr_process": "Umi-OCR.exe",
        "username": "2023114566",
        "password": "2023114566",
        "captcha_region": (1322, 755, 97, 33),
        "target_color": (255, 255, 255),
        "target_pos_2": (1320, 590),
        "target_color_2": (166, 202, 240),
        "target_color_3": (240, 240, 240),
        "coords": {
            "window_check": (1320, 660),
            "username": (1320, 630),
            "password": (1320, 700),
            "captcha_input": (1280, 780),
            "confirm": (1205, 845)
        },
        "max_wait_ocr": 10
    }
    main(login_config)
    time.sleep(2)
