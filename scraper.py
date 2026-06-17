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


FILL_DATES_JS = """
(args) => {
    const debut = args[0];
    const fin = args[1];
    const inputs = Array.from(document.querySelectorAll('input[type="text"]'))
        .filter(el => {
            const rect = el.getBoundingClientRect();
            return rect.width > 0 && rect.height > 0;
        });
    if (inputs.length >= 2) {
        inputs[0].value = debut;
        inputs[0].dispatchEvent(new Event('change', {bubbles: true}));
        inputs[0].dispatchEvent(new Event('blur', {bubbles: true}));
        inputs[1].value = fin;
        inputs[1].dispatchEvent(new Event('change', {bubbles: true}));
        inputs[1].dispatchEvent(new Event('blur', {bubbles: true}));
        return inputs.length;
    }
    return 0;
}
"""

SELECT_TOUTES_JS = """
() => {
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
"""

CLICK_RECHERCHE_JS = """
() => {
    const btns = Array.from(document.querySelectorAll('input, button'));
    const btn = btns.find(b => b.value === 'Recherche' || b.innerText === 'Recherche');
    if (btn) btn.click();
}
"""

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
        bodyTextSample: document.body.innerText.substring(0, 500)
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

        print("[3/6] Remplissage dates...")
        await page.wait_for_timeout(2000)

        date_debut_str = DATE_DEBUT.strftime(FMT)
        date_fin_str = DATE_FIN.strftime(FMT)
        print(f"Dates: {date_debut_str} -> {date_fin_str}")

        filled = await page.evaluate(FILL_DATES_JS, [date_debut_str, date_fin_str])
        print(f"Inputs visibles remplis: {filled}")
        await page.wait_for_timeout(1000)

        await page.evaluate(SELECT_TOUTES_JS)

        print("[4/6] Clic Recherche...")
        try:
            await page.click('input[value="Recherche"]', timeout=10000)
            print("Cliqué via input[value=Recherche]")
        except Exception as e:
            print(f"Echec clic direct: {e}")
            await page.evaluate(CLICK_RECHERCHE_JS)
            print("Cliqué via JS")

        await page.wait_for_timeout(6000)

        print("[5/6] Diagnostic page de résultats...")
        diag = await page.evaluate(DIAGNOSTIC_JS)
        print(f"Nb tables trouvées: {diag['nbTables']}")
        print(f"Info tables: {diag['tablesInfo']}")
        print(f"Extrait texte page: {diag['bodyTextSample']}")

        print("[6/6] Extraction tableau...")
        rows = await page.evaluate(EXTRACT_ROWS_JS)

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
