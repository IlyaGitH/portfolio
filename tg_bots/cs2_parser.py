import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import requests
from bs4 import BeautifulSoup
import re
import time

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def find_item_on_market(item_name, count=10):
    url = "https://steamcommunity.com/market/search/render/"
    params = {
        "query": item_name,
        "start": "0",
        "count": str(count),
        "search_descriptions": "0",
        "sort_column": "price",
        "sort_dir": "asc",
        "appid": "730",  # CS2
        "category_730_Quality[]": "tag_normal"
    }

    response = requests.get(url, params=params)
    response.raise_for_status()
    time.sleep(1)

    item_id_pattern = r"Market_LoadOrderSpread\( (?P<item_id>\d+) \)"
    soup = BeautifulSoup(response.json()["results_html"], "html.parser")

    results = []
    for result in soup.select("a.market_listing_row_link"):
        item_url = result["href"]
        product_name = result.select_one("span.market_listing_item_name").text
        wear = None

        wear_element = result.select_one("span.market_listing_wearable_value")
        if wear_element:
            wear = wear_element.text.strip()

        try:
            response = requests.get(item_url)
            response.raise_for_status()
            time.sleep(1)

            item_id_match = re.search(item_id_pattern, response.text)
            assert item_id_match is not None
        except Exception as e:
            logger.error(f"Skipping {product_name} due to error: {e}")
            continue

        histogram_url = "https://steamcommunity.com/market/itemordershistogram"
        histogram_params = {
            "country": "DE",
            "language": "english",
            "currency": "1",
            "item_nameid": item_id_match.group("item_id"),
            "two_factor": "0"
        }

        response = requests.get(histogram_url, params=histogram_params)
        response.raise_for_status()
        time.sleep(1)

        data = response.json()
        highest_buy_order = float(data["highest_buy_order"]) / 100.0

        results.append({
            "name": product_name,
            "price": highest_buy_order,
            "wear": wear
        })
    return results

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот для поиска предметов из CS2 на Steam Market.\n"
        "Введите команду /find <название предмета> [количество], чтобы найти предмет.\n"
        "Пример: /find AK-47 5"
    )

async def find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("Пожалуйста, укажите название предмета.")
        return

    item_name = " ".join(args[:-1]) if len(args) > 1 else args[0]
    try:
        count = int(args[-1]) if len(args) > 1 else 1
        if count < 1 or count > 10:
            await update.message.reply_text("Количество ордеров должно быть от 1 до 10.")
            return
    except ValueError:
        await update.message.reply_text("Количество ордеров должно быть числом.")
        return

    await update.message.reply_text(f"Ищу предмет: {item_name} (количество ордеров: {count})...")

    try:
        items = find_item_on_market(item_name, count)
        if not items:
            await update.message.reply_text("Предметы не найдены.")
            return

        for item in items:
            message = f"Предмет: {item['name']}\nЦена: ${item['price']:.2f}"
            if item['wear']:
                message += f"\nИзнос: {item['wear']}"
            await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"Ошибка при поиске предмета: {e}")
        await update.message.reply_text("Произошла ошибка при поиске предмета.")

def main():
    token = "7638195295:AAHFjuOq8EQUwVxhl1BVkGv98d3OrswBjqk"

    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("find", find))
    application.run_polling()

if __name__ == "__main__":
    main()