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


DIAGNOSTIC_JS = """
() => {
    const tables = document.querySelectorAll('table');
    const info = [];
    tables.forEach((t, i) => {
        info.push({index: i, rows: t.querySelectorAll('tr').length});
    });
    return {
        nbTables: tables.length,
        tablesInfo: info,
        bodyTextSample: document.body.innerText.substring(0, 800)
    };
}
"""

EXTRACT_ROWS_JS = """
() => {
    const results = [];
    const tables = document.querySelectorAll('table');
    if (!tables.length) return results;

    let table = tables[0];
    let maxRows = 0;
    tables.forEach(t => {
        const n = t.querySelectorAll('tr').length;
        if (n > maxRows) { maxRows = n; table = t; }
    });

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
            dateExpedition: cells[1] ? cells[1].innerText.trim() : '',
            recepisse: cells[2] ? cells[2].innerText.trim() : '',
            votreReference: cells[3] ? cells[3].innerText.trim() : '',
            dateLivraison: cells[4] ? cells[4].innerText.trim() : '',
            destinataire: cells[5] ? cells[5].innerText.trim() : '',
            pays: cells[6] ? cells[6].innerText.trim() : '',
            dept: cells[7] ? cells[7].innerText.trim() : '',
            ville: cells[8] ? cells[8].innerText.trim() : '',
            poids: cells[9] ? cells[9].innerText.trim() : '',
            nbColis: cells[10] ? cells[10].innerText.trim() : '',
        });
    }
    return results;
}
"""


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

        print("[3/6] Remplissage dates via ID précis...")
        await page.wait_for_selector('#Date1', timeout=15000)
        await page.wait_for_timeout(1000)

        date_debut_str = DATE_DEBUT.strftime(FMT)
        date_fin_str = DATE_FIN.strftime(FMT)
        print(f"Dates: {date_debut_str} -> {date_fin_str}")

        date1 = await page.query_selector('#Date1')
        date2 = await page.query_selector('#Date2')

        if date1:
            await date1.click()
            await date1.fill(date_debut_str)
            await date1.dispatch_event('change')
            await date1.dispatch_event('blur')
            print("Date1 rempli")
        else:
            print("Date1 introuvable !")

        if date2:
            await date2.click()
            await date2.fill(date_fin_str)
            await date2.dispatch_event('change')
            await date2.dispatch_event('blur')
            print("Date2 rempli")
        else:
            print("Date2 introuvable !")

        await page.wait_for_timeout(1000)

        val1 = await page.eval_on_selector('#Date1', 'el => el.value') if date1 else None
        val2 = await page.eval_on_selector('#Date2', 'el => el.value') if date2 else None
        print(f"Valeur Date1 après remplissage: {val1}")
        print(f"Valeur Date2 après remplissage:
