import os
import time
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from telegram import Bot
from telegram.constants import ParseMode

# --- Настройки ---
# Читаем токен из защищенных настроек GitHub
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = "@hamyononline"

TEMPLATE_IMAGE = "1.png"
FONT_PATH = "Roboto-Medium.ttf"  # Убедитесь, что шрифт лежит рядом со скриптом
URL = "https://dovtalabonline.tj/currency"

bot = Bot(token=BOT_TOKEN)


def get_currency_rates():
  """Парсит курсы валют с сайта"""
  response = requests.get(URL)
  if response.status_code != 200:
    print(f"Ошибка доступа к сайту: {response.status_code}")
    return None

  soup = BeautifulSoup(response.content, "html.parser")
  rates = {}

  # Ищем все карточки валют на основе вашей разметки
  cards = soup.find_all("div", class_="curr-card")
  for card in cards:
    code_elem = card.find("div", class_="curr-code")
    rate_elem = card.find("div", class_="curr-rate")

    if code_elem and rate_elem:
      code = code_elem.text.strip()
      rate = rate_elem.text.strip()
      rates[code] = rate

  return rates


def create_currency_image(rates):
  """Накладывает актуальные курсы и крупную дату на шаблон картинки"""
  try:
    img = Image.open(TEMPLATE_IMAGE)
  except FileNotFoundError:
    print(f"Не найден файл шаблона: {TEMPLATE_IMAGE}")
    return None

  draw = ImageDraw.Draw(img)

  try:
    font = ImageFont.truetype(FONT_PATH, size=75)
    # Увеличили размер шрифта для даты и сделали его заметным
    date_font = ImageFont.truetype(FONT_PATH, size=100)
  except IOError:
    print(f"Не найден файл шрифта: {FONT_PATH}")
    return None

  # 1. Дата: крупная, сдвинута ниже под надпись "на сегодня" (Y = 270)
  today_str = datetime.now().strftime("%d.%m.%Y")
  date_coords = (420, 400)  # Позиция под "на сегодня"
  date_color = (255, 255, 255)  # Светлый, хорошо читаемый оттенок
  
  # Рисуем дату с выравниванием по левому краю или центру (оставляем по центру)
  draw.text(date_coords, today_str, font=date_font, fill=date_color, anchor="mm")

  # 2. Координаты для курсов валют (чуть правее, на середину черточек)
  coordinates = {
      "USD": (640, 590),
      "EUR": (640, 800),
      "RUB": (640, 1010),
      "CNY": (640, 1220),
  }

  text_color = (240, 245, 255)

  for currency, coords in coordinates.items():
    rate_value = rates.get(currency, "----")
    draw.text(
        coords, rate_value, font=font, fill=text_color, anchor="mm"
    )

  output_path = "result_currency.png"
  img.save(output_path)

  return output_path


def job():
  """Основная задача: парсинг, создание картинки и отправка в Telegram"""
  print(f"[{datetime.now()}] Запуск обновления курсов валют...")

  rates = get_currency_rates()
  if not rates:
    print("Не удалось получить курсы валют.")
    return

  # Проверяем наличие нужных валют
  required = ["USD", "EUR", "RUB", "CNY"]
  if not all(k in rates for k in required):
    print("Не все обязательные валюты найдены на странице.")
    return

  image_path = create_currency_image(rates)
  if not image_path:
    return

  # Формируем подпись к картинке
  today_str = datetime.now().strftime("%d.%m.%Y")
  caption = f"📊 **Официальный курс валют на сегодня** ({today_str})\nИсточник: https://dovtalabonline.tj/currency\nПриложение: https://play.google.com/store/apps/details?id=com.neuronit.hamyon"

  # Отправляем фото в канал синхронно
  try:
    with open(image_path, "rb") as photo:
      # Используем send_photo через requests к Telegram API для простоты в sync режиме
      url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
      files = {"photo": photo}
      data = {
          "chat_id": CHANNEL_ID,
          "caption": caption,
          "parse_mode": "Markdown",
      }
      response = requests.post(url, data=data, files=files)
      if response.status_code == 200:
        print("Сообщение успешно отправлено в Telegram!")
      else:
        print(f"Ошибка отправки в Telegram: {response.text}")
  except Exception as e:
    print(f"Произошла ошибка при отправке: {e}")


# --- Планировщик ---
# Запуск задачи при старте скрипта (GitHub сам вызовет её в нужное время)
if __name__ == "__main__":
    job()
