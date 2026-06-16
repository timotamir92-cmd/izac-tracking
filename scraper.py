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

        print(f"[2/5] Connexion {NOM}...")
        await page.fill('input[type="text"]', NOM)
        await page.fill('input[type="password"]', MDP)
        await page.click('input[value="Valider"], button:has-text("Valider")')
        await page.wait_for_timeout(4000)
        print(f"URL après login: {page.url}")

        print("[3/5] Remplissage dates via JavaScript...")
        await page.wait_for_timeout(2000)

        date_debut_str = DATE_DEBUT.strftime(FMT)
        date_fin_str = DATE_FIN.strftime(FMT)
        print(f"Dates: {date_debut_str} -> {date_fin_str}")

        # Remplir les 2 premiers champs texte visibles via JS directement
        filled = await page.evaluate(f"""
        () => {{
            const inputs = Array.from(document.querySelectorAll('input[type="text"]'))
                .filter(el => {{
                    const rect = el.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0;
                }});
            console.log('Inputs visibles:', inputs.length);
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

        print("[4/5] Clic Recherche...")
        try:
            await page.click('input[value="Recherche"]', timeout=10000)
            print("Cliqué via input[value=Recherche]")
        except:
            await page.evaluate("""
            () => {
                const btns = Array.from(document.querySelectorAll('input, button'));
                const btn = btns.find(b => b.value === 'Recherche' || b.innerText === 'Recherche');
                if (btn) btn.click();
            }
            """)
            print("Cliqué via JS")

        await page.wait_for_timeout(5000)

        print("[5/5] Extraction tableau...")
        rows = await page.evaluate("""
        () => {
            const results = [];
            const tables = document.querySelectorAll('table');
            if (!tables.length) return results;
            const table = tables[0];
            const trows = table.querySelectorAll('tr');
            for (let i = 1; i < trows.length; i++) {
                const cells = trows[i].querySelectorAll('td');
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
        print(f"{len(rows)} expéditions extraites")

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
