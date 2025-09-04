import asyncio
import json
import requests
from bs4 import BeautifulSoup
from telegram.ext import Application
import urllib.parse
import os
from dotenv import load_dotenv
load_dotenv()

# =========================
# 🔧 CONFIG
# =========================
CITIES = ["den-haag", "rotterdam", "utrecht", "amsterdam", "lieden", "delft"]  # add/remove as needed
PRICE_RANGE = "0-1750"
BEDROOMS = "2-slaapkamers"
NEW_FILTER = "sinds-1"  # last 1 hour

BASE_URL = "https://www.pararius.nl/huurwoningen/{city}/{price}/{bedrooms}/{new}"

CHECK_INTERVAL = 600  # seconds (10 min)
STATE_FILE = "seen_listings.json"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))


# =========================
# 📂 Helpers
# =========================
def load_seen():
    try:
        with open(STATE_FILE, "r") as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()


def save_seen(seen):
    with open(STATE_FILE, "w") as f:
        json.dump(list(seen), f)


def fetch_listings(url, city):
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers)
    soup = BeautifulSoup(resp.text, "html.parser")

    listings = []
    for item in soup.select("section.listing-search-item"):
        link_tag = item.select_one("a.listing-search-item__link")
        if not link_tag:
            continue

        link = "https://www.pararius.nl" + link_tag["href"]
        title = link_tag.get_text(strip=True)

        price_tag = item.select_one("div.listing-search-item__price")
        price = price_tag.get_text(strip=True) if price_tag else "N/A"

        address_tag = item.select_one("div.listing-search-item__sub-title")
        address = address_tag.get_text(strip=True) if address_tag else "N/A"

        listings.append(
            {
                "id": link,
                "title": title,
                "price": price,
                "url": link,
                "address": address,
                "city": city,
            }
        )
    return listings


def fetch_agency_info(listing_url):
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(listing_url, headers=headers)
    soup = BeautifulSoup(resp.text, "html.parser")

    agency_name, agency_url = "N/A", "N/A"
    agency_block = soup.select_one("div.agent-profile__name a")
    if agency_block:
        agency_name = agency_block.get_text(strip=True)
        agency_url = agency_block["href"]

    return agency_name, agency_url


def build_email_draft(listing):
    subject = f"Aanvraag voor {listing['title']} - {listing['address']}"
    body = f"""Geachte heer/mevrouw,

Mijn naam is Aluny en samen met mijn vrouwelijke huisgenoot Yana wil ik graag reageren op de bovenwoning in {listing['address']}. Wij zijn erg geïnteresseerd in de woning en kunnen per direct intrekken.

Graag stellen wij ons kort voor:
• Ik ben Duitse studente en volg momenteel mijn masteropleiding aan de Universiteit Utrecht. Daarnaast loop ik stage als Digital Experience Designer bij Adidas.
• Mijn huisgenoot is eveneens internationale studente. Zij rondt dit jaar haar bacheloropleiding aan De Haagse Hogeschool af en loopt stage bij ASML.
• Wij beiden zijn van plan om ons voor langere tijd in Nederland te vestigen en, na afronding van onze studies, door te stromen naar fulltime functies.

Wij zijn niet-rokers, rustig en hechten veel waarde aan een schoon en verzorgd woonklimaat. Wij zoeken een stabiele en langdurige woonruimte waarin wij ons volledig kunnen richten op studie en professionele ontwikkeling.

Financieel worden wij volledig ondersteund door onze garantstellers, waarmee wij ruimschoots aan de inkomenseisen voldoen. Indien gewenst kunnen wij alle benodigde documenten aanleveren, waaronder inkomensverklaringen van de garantstellers, bewijs van inschrijving, stageovereenkomsten en identiteitsbewijzen.

Wij zijn zeer gemotiveerd om deze woning te huren en voorzien u graag van aanvullende informatie of maken een afspraak voor een bezichtiging op korte termijn.

Bij voorbaat hartelijk dank voor uw overweging. Wij kijken uit naar uw reactie.

Met vriendelijke groet,
Aluny Griendl
+31 684 608 976
aluny.g@gmail.com
"""

    subject_enc = urllib.parse.quote(subject)
    body_enc = urllib.parse.quote(body)

    # no recipient → you’ll type it manually in Mail
    mailto_url = f"mailto:?subject={subject_enc}&body={body_enc}"

    return f"📩 [Stuur een e-mail]({mailto_url})"


# =========================
# 🚀 Scraper loop
# =========================
async def scraper_loop(app):
    seen = load_seen()
    print("🤖 Bot started. Monitoring Pararius...")

    while True:
        try:
            for city in CITIES:
                url = BASE_URL.format(city=city, price=PRICE_RANGE, bedrooms=BEDROOMS, new=NEW_FILTER)
                listings = fetch_listings(url, city)
                new_listings = [l for l in listings if l["id"] not in seen]

                for listing in new_listings:
                    agency_name, agency_url = fetch_agency_info(listing["url"])
                    draft_link = build_email_draft(listing)

                    draft_link = build_email_draft(listing)

                    msg = (
                        f"🏙️ [{listing['city'].title()}]\n"
                        f"🏠 {listing['title']}\n"
                        f"📍 {listing['address']}\n"
                        f"💶 {listing['price']}\n"
                        f"🔗 {listing['url']}\n"
                        f"📢 Agency: {agency_name}\n"
                        f"🌐 {agency_url}\n\n"
                        f"{draft_link}"
                    )

                    await app.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
                    seen.add(listing["id"])
                    print(f"📢 New listing sent from {listing['city']}: {listing['title']}")

            save_seen(seen)
        except Exception as e:
            print("⚠️ Error:", e)

        await asyncio.sleep(CHECK_INTERVAL)


# =========================
# 🏁 Main
# =========================
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    async def on_startup(app_):
        asyncio.create_task(scraper_loop(app_))

    app.post_init = on_startup
    app.run_polling()


if __name__ == "__main__":
    main()