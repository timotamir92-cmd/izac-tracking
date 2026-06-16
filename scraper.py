import asyncio
import json
import os
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

LOGIN_URL = "http://pda.transadis.fr/profoundui/traplus?pgm=TRAPLUSPUI/PUITRAPCL&p1=TRACKWEB%20%20----WebTrackingPERON&l1=256&p2=fr_FR&l2=15&lang=fr_FR"

NOM = os.environ.get("TRANSADIS_NOM", "IZAC")
MDP = os.environ.get("TRANSADIS_MDP", "")

DATE_FIN = datetime.today()
DATE_DEBUT = DATE_FIN - timedelta(days=7)
FMT = "%d/%m/%y"

async def scrape():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print("[1/5] Ouverture page connexion...")
        await page.goto(LOGIN_URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(2000)

        print(f"[2/5] Connexion {NOM}...")
        await page.fill('input[type="text"]', NOM)
        await page.fill('input[type="password"]', MDP)
        await page.click('input[value="Valider"], button:has-text("Valider")')
        await page.wait_for_timeout(3000)

        print("[3/5] Formulaire de recherche...")
        await page.wait_for_selector('input[type="text"]', timeout=15000)

        date_debut_str = DATE_DEBUT.strftime(FMT)
