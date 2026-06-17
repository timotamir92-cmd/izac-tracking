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

        print("[1/6] Ouverture page connexion...")
        await page.goto(LOGIN_URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        print(f"[2/6] Connexion {NOM}...")
        await page.fill('input[type="text"]', NOM)
        await page.fill('input[type="password"]', MDP)
        await page.click('input[value="Valider"], button:has-text("Valider")')
        await page.wait_for_timeout(4000)
        print(f"URL après login: {page.url}")

        print("[3/6] Remplissage dates...")
        await page.wait_for_timeout(2000)

        date_debut_str = DATE_DEBUT.strftime(FMT)
        date_fin_str = DATE_FIN.strftime(FMT)
        print(f"Dates: {date_debut_str} -> {date_fin_str}")

        filled = await page.evaluate(f"""
        () => {{
            const inputs = Array.from(document.querySelectorAll('input[type="text"]'))
                .filter(el => {{
                    const rect = el.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0;
                }});
            if (inputs.length >= 2) {{
                inputs[0].value = '{date_debut_str}';
                inputs[0].dispatchEvent(new Event('change', {{bubbles: true}}));
                inputs[0].dispatchEvent(new Event('blur', {{bubbles: true}}));
                inputs[1].value = '{date_fin_str}';
                inputs[1].dispatchEvent(new Event('change', {{bubbles: true}}));
                inputs[1].dispatchEvent(new Event('blur', {{bubbles: true}}));
                return inputs.length;
            }}
            return 0;
        }}
        """)
        print(f"Inputs visibles remplis: {filled}")
        await page.wait_for_timeout(1000)

        # Sélectionner "Toutes" pour être sûr
        await page.evaluate("""
        () => {
            const radios = Array.from(document.querySelectorAll('input[type="radio"]'));
            console.log('radios:', radios.length);
            const labels = Array.from(document.querySelectorAll('label'));
            const toutesLabel = labels.find(l => l.innerText.includes('Toutes'));
            if (toutesLabel) {
                const forId = toutesLabel.getAttribute('for');
                if (forId) {
                    const radio = document.getElementById(forId);
                    if (radio) radio.click();
                }
            }
        }
        """)

        print("[4/6] Clic Recherche...")
        try:
            await page.click('input[value="Recherche"]', timeout=10000)
            print("Cliqué via input[value=Recherche]")
        except Exception as e:
            print(f"Echec clic direct: {e}")
            await page.evaluate("""
            () => {
                const btns =
