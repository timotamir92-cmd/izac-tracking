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
        await page.wait_for_timeout(3000)
        await page.screenshot(path="debug_1_login.png")
        print("Screenshot 1 sauvegardé")

        print(f"[2/5] Connexion {NOM}...")
        inputs = await page.query_selector_all('input[type="text"], input[type="password"]')
        print(f"Inputs trouvés: {len(inputs)}")
        for i, inp in enumerate(inputs):
            t = await inp.get_attribute('type')
            n = await inp.get_attribute('name')
            print(f"  input[{i}] type={t} name={n}")

        await page.fill('input[type="text"]', NOM)
        await page.fill('input[type="password"]', MDP)
        await page.screenshot(path="debug_2_filled.png")

        await page.click('input[value="Valider"], button:has-text("Valider")')
        await page.wait_for_timeout(4000)
        await page.screenshot(path="debug_3_after_login.png")
        print("Screenshot 3 sauvegardé - après login")
        print(f"URL après login: {page.url}")

        print("[3/5] Attente page tracking...")
        await page.wait_for_timeout(3000)
        await page.screenshot(path="debug_4_tracking.png")

        # Afficher tous les inputs visibles
        all_inputs = await page.query_selector_all('input')
        print(f"Total inputs sur la page: {len(all_inputs)}")
        for i, inp in enumerate(all_inputs[:10]):
            t = await inp.get_attribute('type')
            n = await inp.get_attribute('name')
            v = await inp.get_attribute('value')
            print(f"  input[{i}] type={t} name={n} value={v}")

        # Chercher le bouton Recherche
        btns = await page.query_selector_all('input[type="submit"], button, input[type="button"]')
        print(f"Boutons trouvés: {len(btns)}")
        for b in btns[:5]:
            v = await b.get_attribute('value')
            t = await b.inner_text() if await b.get_attribute('type') != 'submit' else ''
            print(f"  bouton: value={v} text={t}")

        # Remplir les dates
        date_debut_str = DATE_DEBUT.strftime(FMT)
        date_fin_str = DATE_FIN.strftime(FMT)
        print(f"Dates: {date_debut_str} → {date_fin_str}")

        text_inputs = await page.query_selector_all('input[type="text"]')
        print(f"Inputs text trouvés: {len(text_inputs)}")
        if len(text_inputs) >= 2:
            await text_inputs[0].click()
            await text_inputs[0].fill(date_debut_str)
            await text_inputs[1].click()
            await text_inputs[1].fill(date_fin_str)
            print("Dates remplies")

        await page.screenshot(path="debug_5_dates.png")

        # Cliquer Recherche
        try:
            await page.click('input[value="Recherche"]')
            print("Bouton Recherche cliqué (input)")
        except:
            try:
                await page.click('button:has-text("Recherche")')
                print("Bouton Recherche cliqué (button)")
            except Exception as e:
                print(f"Impossible de cliquer Recherche: {e}")

        await page.wait_for_timeout(4000)
        await page.screenshot(path="debug_6_results.png")

        print("[4/5] Extraction tableau...")
        html = await page.content()
        print(f"Taille HTML: {len(html)} chars")

        rows = await page.evaluate("""
        () => {
            const results = [];
            const tables = document.querySelectorAll('table');
            console.log('Tables trouvées:', tables.length);
            if (!tables.length) return results;
            const table = tables[0];
            const rows = table.querySelectorAll('tr');
            for (let i = 1; i < rows.length; i++) {
                const cells = rows[i].querySelectorAll('td');
                if (cells.length < 8) continue;
                const statutImg = cells[0].querySelector('img');
                let statut = 'En cours';
                if (statutImg) {
                    const src = statutImg.src || '';
                    if (src.includes('livreconforme') && !src.includes('non')) statut = 'Livré conforme';
                    else if (src.includes('nonconforme')) statut = 'Livré non conforme';
                    else if (src.includes('anomalie')) statut = 'Anomalie';
                    else if (src.includes('souffrance')) statut = 'Souffrance';
                }
                results.push({
                    statut,
                    dateExpedition: cells[1]?.innerText?.trim() || '',
                    recepisse: cells[2]?.innerText?.trim() || '',
                    votreReference: cells[3]?.innerText?.trim() || '',
                    dateLivraison: cells[4]?.innerText?.trim() || '',
                    destinataire: cells[5]?.innerText?.trim() || '',
                    pays: cells[6]?.innerText?.trim() || '',
                    dept: cells[7]?.innerText?.trim() || '',
                    ville: cells[8]?.innerText?.trim() || '',
                    poids: cells[9]?.innerText?.trim() || '',
                    nbColis: cells[10]?.innerText?.trim() || '',
                });
            }
            return results;
        }
        """)

        await browser.close()
        print(f"[5/5] {len(rows)} expéditions extraites")

        # Générer data.json même si vide pour éviter l'erreur git
        output = {
            "lastUpdate": datetime.now().isoformat(),
            "periode": {
                "debut": DATE_DEBUT.strftime("%d/%m/%Y"),
                "fin": DATE_FIN.strftime("%d/%m/%Y")
            },
            "total": len(rows),
            "expeditions": rows
        }

        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print("✅ data.json généré")

if __name__ == "__main__":
    asyncio.run(scrape())
