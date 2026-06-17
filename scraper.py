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
    const grids = document.querySelectorAll('[class*="traplus-grid"], [puiwdgt="grid"]');
    const gridsInfo = [];
    grids.forEach(g => {
        const cells = g.querySelectorAll('[class*="cell"]');
        gridsInfo.push({
            id: g.id,
            className: g.className,
            nbChildren: g.children.length,
            nbCells: cells.length,
            sample: Array.from(cells).slice(0, 5).map(c => ({
                className: c.className,
                text: c.innerText.trim().substring(0, 40)
            }))
        });
    });

    const rows = document.querySelectorAll('[class*="row"]');
    const rowsInfo = [];
    rows.forEach((r, i) => {
        if (i < 10) {
            rowsInfo.push({
                className: r.className,
                id: r.id,
                text: r.innerText.trim().substring(0, 60)
            });
        }
    });

    return {
        nbGrids: grids.length,
        gridsInfo: gridsInfo,
        nbRowLike: rows.length,
        rowsInfo: rowsInfo
    };
}
"""

EXTRACT_ROWS_JS = """
() => {
    function findBestTable(doc) {
        const tables = doc.querySelectorAll('table');
        let best = null;
        let maxRows = 0;
        tables.forEach(t => {
            const n = t.querySelectorAll('tr').length;
            if (n > maxRows) { maxRows = n; best = t; }
        });
        return best;
    }

    function extractFromTable(table) {
        const results = [];
        if (!table) return results;
        const trows = table.querySelectorAll('tr');
        for (let i = 1; i < trows.length; i++) {
            const cells = trows[i].querySelectorAll('td');
            if (cells.length < 8) continue;
            const statutImg = cells[0].querySelector('img');
            let statut = 'En cours';
            if (statutImg) {
                const src = statutImg.src || '';
                if (src.indexOf('livreconforme') !== -1 && src.indexOf('non') === -1) statut = 'Livre conforme';
                else if (src.indexOf('nonconforme') !== -1) statut = 'Livre non conforme';
                else if (src.indexOf('anomalie') !== -1) statut = 'Anomalie';
                else if (src.indexOf('souffrance') !== -1) statut = 'Souffrance';
            }
            results.push({
                statut: statut,
                dateExpedition: cells[1] ? cells[1].innerText.trim() : '',
                recepisse: cells[2] ? cells[2].innerText.trim() : '',
                votreReference: cells[3] ? cells[3].innerText.trim() : '',
                dateLivraison: cells[4] ? cells[4].innerText.trim() : '',
                destinataire: cells[5] ? cells[5].innerText.trim() : '',
                pays: cells[6] ? cells[6].innerText.trim() : '',
                dept: cells[7] ? cells[7].innerText.trim() : '',
                ville: cells[8] ? cells[8].innerText.trim() : '',
                poids: cells[9] ? cells[9].innerText.trim() : '',
                nbColis: cells[10] ? cells[10].innerText.trim() : ''
            });
        }
        return results;
    }

    let allDocs = [document];
    const iframes = document.querySelectorAll('iframe');
    iframes.forEach(f => {
        try {
            if (f.contentDocument) allDocs.push(f.contentDocument);
        } catch (e) {}
    });

    let bestTable = null;
    let bestDoc = null;
    let maxRows = 0;
    allDocs.forEach(doc => {
        const t = findBestTable(doc);
        if (t) {
            const n = t.querySelectorAll('tr').length;
            if (n > maxRows) { maxRows = n; bestTable = t; bestDoc = doc; }
        }
    });

    return extractFromTable(bestTable);
}
"""


async def scrape():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print("[1/6] Ouverture page connexion")
        await page.goto(LOGIN_URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        print("[2/6] Connexion " + NOM)
        await page.fill('input[type="text"]', NOM)
        await page.fill('input[type="password"]', MDP)
        await page.click('input[value="Valider"], button:has-text("Valider")')
        await page.wait_for_timeout(4000)
        print("URL apres login: " + page.url)

        print("[3/6] Remplissage dates via ID precis")
        await page.wait_for_selector('#Date1', timeout=15000)
        await page.wait_for_timeout(1000)

        date_debut_str = DATE_DEBUT.strftime(FMT)
        date_fin_str = DATE_FIN.strftime(FMT)
        print("Dates: " + date_debut_str + " -> " + date_fin_str)

        date1 = await page.query_selector('#Date1')
        date2 = await page.query_selector('#Date2')

        if date1:
            await date1.click()
            await date1.fill(date_debut_str)
            await date1.dispatch_event('change')
            await date1.dispatch_event('blur')
            print("Date1 rempli")
        else:
            print("Date1 introuvable")

        if date2:
            await date2.click()
            await date2.fill(date_fin_str)
            await date2.dispatch_event('change')
            await date2.dispatch_event('blur')
            print("Date2 rempli")
        else:
            print("Date2 introuvable")

        await page.wait_for_timeout(1000)

        val1 = await page.eval_on_selector('#Date1', 'el => el.value') if date1 else None
        val2 = await page.eval_on_selector('#Date2', 'el => el.value') if date2 else None
        print("Valeur Date1 apres remplissage: " + str(val1))
        print("Valeur Date2 apres remplissage: " + str(val2))

        await page.screenshot(path="debug_before_click.png")
        print("Screenshot avant clic sauvegarde")

        print("[4/6] Clic Recherche via ID btn_rch")
        try:
            await page.click('#btn_rch', timeout=10000)
            print("Clique via btn_rch")
        except Exception as e:
            print("Echec clic btn_rch: " + str(e))
            try:
                await page.click('input[value="Recherche"]', timeout=5000)
                print("Clique via input value Recherche")
            except Exception as e2:
                print("Echec total clic recherche: " + str(e2))

        print("Attente chargement resultats")
        await page.wait_for_timeout(4000)

        await page.wait_for_timeout(2000)

        await page.screenshot(path="debug_after_click.png")
        print("Screenshot apres clic sauvegarde")

        print("[5/6] Diagnostic page de resultats")
        diag = await page.evaluate(DIAGNOSTIC_JS)
        print("Nb grids trouves: " + str(diag['nbGrids']))
        print("Grids info: " + str(diag['gridsInfo']))
        print("Nb elements row-like: " + str(diag['nbRowLike']))
        print("Rows info: " + str(diag['rowsInfo']))

        print("[6/6] Extraction tableau (desactivee pour diagnostic)")
        rows = []

        await browser.close()
        print(str(len(rows)) + " expeditions extraites")

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
        print("data.json genere")


if __name__ == "__main__":
    asyncio.run(scrape())
