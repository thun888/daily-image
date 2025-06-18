import os
import requests
from PIL import Image
from io import BytesIO
from datetime import datetime
import logging
import zipfile
import telegram
import asyncio

# 日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 路径配置
STATIC_FOLDER = "static"
DAILY_IMAGE_PATH = os.path.join(STATIC_FOLDER, "daily.webp")
DAILY_JPEG_PATH = os.path.join(STATIC_FOLDER, "daily.jpeg")
ORIGINAL_JPEG_PATH = os.path.join(STATIC_FOLDER, "original.jpeg")

# Telegram 配置 从环境变量读取
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")

# 确保文件夹存在
os.makedirs(STATIC_FOLDER, exist_ok=True)

def fetch_bing_image():
    """获取今天的Bing壁纸信息"""
    try:
        url = "https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1&uhd=1"
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()
        image = data["images"][0]
        date = datetime.strptime(image["enddate"], "%Y%m%d").strftime("%Y-%m-%d")
        logging.info(f"获取到图片: {date}")
        urlbase = image["urlbase"]
        high_res_url = f"https://www.bing.com{urlbase}_UHD.jpg"
        fallback_url = f"https://www.bing.com{urlbase}_1920x1080.jpg"

        test_resp = requests.head(high_res_url)
        image_url = high_res_url if test_resp.status_code == 200 else fallback_url

        return {
            "date": date,
            "url": image_url,
            "copyright": image.get("copyright", "")
        }
    except Exception as e:
        logging.error(f"获取 Bing 图片信息失败: {e}")
        return None

def download_image(url):
    """下载图片并返回PIL Image对象"""
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        return Image.open(BytesIO(resp.content)).convert("RGB")
    except Exception as e:
        logging.error(f"下载图片失败: {e}")
        return None

def save_image(img, filepath, format="WEBP"):
    """保存图片到指定路径"""
    try:
        if format == "WEBP":
            img.save(filepath, "WEBP", quality=80, method=6)
        elif format == "JPEG":
            img.save(filepath, "JPEG", quality=100, optimize=True)
        logging.info(f"保存图片 {filepath}")
        return True
    except Exception as e:
        logging.error(f"保存图片失败 {filepath}: {e}")
        return False

def create_zip_file(date, image_path):
    """创建包含图片的zip文件"""
    zip_filename = f"{date}.zip"
    zip_filepath = os.path.join(STATIC_FOLDER, zip_filename)
    try:
        with zipfile.ZipFile(zip_filepath, 'w') as zipf:
            zipf.write(image_path, os.path.basename(image_path))
        logging.info(f"创建zip文件: {zip_filepath}")
        return zip_filepath
    except Exception as e:
        logging.error(f"创建zip文件失败: {e}")
        return None

async def upload_to_telegram(bot, channel_id, jpeg_path, zip_path, copyright_text, date):
    """上传文件到Telegram频道"""
    try:
        # 第一条消息：发送图片，附带版权信息和日期
        caption = f"{copyright_text} ({date})"
        with open(jpeg_path, 'rb') as photo:
            await bot.send_photo(chat_id=channel_id, photo=photo, caption=caption)
        logging.info(f"上传图片 {jpeg_path} 成功，附带描述: {caption}")

        # 第二条消息：发送压缩包
        with open(zip_path, 'rb') as document:
            await bot.send_document(chat_id=channel_id, document=document)
        logging.info(f"上传zip文件 {zip_path} 成功")
    except Exception as e:
        logging.error(f"上传到Telegram失败: {e}")

async def main():
    logging.info("开始获取 Bing 图片...")
    image_info = fetch_bing_image()

    if not image_info:
        logging.error("未获取到今天的图像信息")
        return

    date = image_info["date"]
    img = download_image(image_info["url"])

    if img is None:
        return

    # 保存图片
    save_image(img, DAILY_IMAGE_PATH, "WEBP")
    save_image(img, DAILY_JPEG_PATH, "JPEG")
    save_image(img, ORIGINAL_JPEG_PATH, "JPEG")

    # 重命名 daily.jpeg 为 {date}.jpeg
    date_jpeg_path = os.path.join(STATIC_FOLDER, f"{date}.jpeg")
    os.rename(DAILY_JPEG_PATH, date_jpeg_path)
    logging.info(f"重命名 daily.jpeg 为 {date}.jpeg")

    # 创建zip文件
    zip_path = create_zip_file(date, DAILY_IMAGE_PATH)

    if zip_path is None:
        return

    # 上传到Telegram
    bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
    await upload_to_telegram(bot, TELEGRAM_CHANNEL_ID, date_jpeg_path, zip_path, image_info["copyright"], date)

if __name__ == "__main__":
    asyncio.run(main())