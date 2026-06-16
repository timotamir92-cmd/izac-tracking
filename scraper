"""
Transadis Traplus - Web Tracking Scraper
Connexion automatique + export des expéditions du jour en JSON
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

LOGIN_URL = "http://pda.transadis.fr/profoundui/traplus?pgm=TRAPLUSPUI/PUITRAPCL&p1=TRACKWEB%20%20----WebTrackingPERON&l1=256&p2=fr_FR&l2=15&lang=fr_FR"

# Credentials depuis GitHub Secrets
NOM = os.environ.get("TRANSADIS_NOM", "IZAC")
MDP = os.environ.get("TRANSADIS_MDP", "")

# Période : 7 derniers jours par défaut
DATE_FIN = datetime.today()
DATE_DEBUT = DATE_FIN - timedelta(days=7)
FMT = "%d/%m/%y"


async def scrape():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print(f"[1/5] Ouverture de la page de connexion...")
        await page.goto(LOGIN_URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(2000)

        print(f"[2/5] Connexion avec le compte {NOM}...")
        # Remplir le formulaire de login
        await page.fill('input[name*="nom"], input[id*="nom"], input[type="text"]', NOM)
        await page.fill('input[name*="passe"], input[id*="passe"], input[type="password"]', MDP)
        await page.click('input[type="submit"], button[type="submit"], input[value="Valider"]')
        await page.wait_for_timeout(3000)

        print(f"[3/5] Remplissage du formulaire de recherche...")
        # Attendre que la page de tracking soit chargée
        await page.wait_for_selector('input[type="text"]', timeout=15000)

        # Remplir les dates
        date_debut_str = DATE_DEBUT.strftime(FMT)
        date_fin_str = DATE_FIN.strftime(FMT)

        # Chercher les champs de date
        date_inputs = await page.query_selector_all('input[type="text"]')
        if len(date_inputs) >= 2:
            await date_inputs[0].triple_click()
            await date_inputs[0].type(date_debut_str)
            await date_inputs[1].triple_click()
            await date_inputs[1].type(date_fin_str)

        # Sélectionner "Toutes" les expéditions
        try:
            await page.click('input[type="radio"][value*="Toutes"], label:has-text("Toutes")')
        except:
            pass

        # Cliquer Recherche
        await page.click('input[value="Recherche"], button:has-text("Recherche")')
        await page.wait_for_timeout(3000)

        print(f"[4/5] Extraction des données du tableau...")
        # Extraire toutes les lignes du tableau
        rows = await page.evaluate("""
        () => {
            const results = [];
            const table = document.querySelector('table');
            if (!table) return results;
            
            const rows = table.querySelectorAll('tr');
            for (let i = 1; i < rows.length; i++) { // skip header
                const cells = rows[i].querySelectorAll('td');
                if (cells.length < 8) continue;
                
                // Récupérer le statut depuis l'image/icône
                const statutImg = cells[0].querySelector('img');
                let statut = 'En cours';
                if (statutImg) {
                    const src = statutImg.src || '';
                    if (src.includes('livreconforme')) statut = 'Livré conforme';
                    else if (src.includes('livrenonconforme')) statut = 'Livré non conforme';
                    else if (src.includes('anomalie')) statut = 'Anomalie';
                    else if (src.includes('souffrance')) statut = 'Souffrance';
                    else if (src.includes('information')) statut = 'Information';
                    else if (src.includes('rdv')) statut = 'Rendez-vous';
                }
                
                results.push({
                    statut: statut,
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
                    preuveLivraison: cells[11]?.innerText?.trim() || '',
                    le: cells[12]?.innerText?.trim() || '',
                });
            }
            return results;
        }
        """)

        await browser.close()

        print(f"[5/5] {len(rows)} expéditions extraites → écriture data.json")

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

        print("✅ data.json généré avec succès")
        return output


if __name__ == "__main__":
    asyncio.run(scrape())
