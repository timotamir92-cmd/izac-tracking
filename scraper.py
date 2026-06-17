import asyncio
import json
import os
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

LOGIN_URL = "http://pda.transadis.fr/profoundui/traplus?pgm=TRAPLUSPUI/PUITRAPCL&p1=TRACKWEB%20%20----WebTrackingPERON&l1=256&p2=fr_FR&l2=15&lang=fr_FR"

NOM = os.environ.get("TRANSADIS_NOM", "IZAC")
MDP = os.environ.get("TRANSADIS_MDP", "")

DATE_FIN = datetime.today()
DATE_DEBUT = DATE_FIN - timedelta(days=30)
FMT = "%d/%m/%y"

DOWNLOAD_PATH = "export_traplus.xlsx"

EXPORT_SELECTORS = [
    ".xlsx-paging-link",
    "span.xlsx-paging-link",
    "span:has-text('Exporter vers Excel')",
    "[class*='xlsx-paging']",
]


def statut_from_text(raw):
    if not raw:
        return "En cours"
    t = str(raw).strip().lower()
    if "anomalie" in t and "livr" in t:
        return "Anomalie"
    if "anomalie" in t:
        return "Anomalie"
    if "souffrance" in t:
        return "Souffrance"
    if "non conforme" in t:
        return "Livre non conforme"
    if "livr" in t:
        return "Livre conforme"
    return "En cours"


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

        if date2:
            await date2.click()
            await date2.fill(date_fin_str)
            await date2.dispatch_event('change')
            await date2.dispatch_event('blur')
            print("Date2 rempli")

        await page.wait_for_timeout(1000)

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
        await page.wait_for_timeout(6000)
        await page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(1000)

        await page.screenshot(path="debug_before_export.png")
        print("Screenshot avant export sauvegarde")

        print("[5/6] Recherche bouton Exporter vers Excel")
        export_clicked = False
        used_selector = None
        for sel in EXPORT_SELECTORS:
            try:
                el = await page.query_selector(sel)
                if el:
                    is_visible = await el.is_visible()
                    if is_visible:
                        used_selector = sel
                        break
            except Exception:
                continue

        if not used_selector:
            print("ERREUR: aucun bouton export trouve avec les selecteurs connus")
            print("Listing de tous les liens/boutons visibles pour diagnostic:")
            diag = await page.evaluate(
                "() => Array.from(document.querySelectorAll('a, button, input[type=button], img')) "
                ".filter(e => e.offsetParent !== null) "
                ".map(e => ({tag: e.tagName, text: (e.innerText || e.alt || e.value || '').trim().substring(0,40), id: e.id, title: e.title})) "
                ".filter(e => e.text || e.title)"
            )
            print(str(diag))

            print("Recherche large du mot Excel ou Exporter dans tout le DOM")
            wide_search = await page.evaluate(
                "() => { "
                "const all = Array.from(document.querySelectorAll('*')); "
                "const matches = all.filter(e => { "
                "  const txt = (e.innerText || e.textContent || '').trim(); "
                "  return txt.length < 60 && (txt.toLowerCase().includes('excel') || txt.toLowerCase().includes('export')); "
                "}); "
                "return matches.slice(0, 20).map(e => ({tag: e.tagName, id: e.id, cls: e.className, text: (e.innerText||e.textContent||'').trim().substring(0,60)})); "
                "}"
            )
            print("Resultats recherche large: " + str(wide_search))

            print("Nb iframes sur la page: " + str(await page.evaluate("() => document.querySelectorAll('iframe').length")))

            rows = []
        else:
            print("Bouton trouve avec selecteur: " + used_selector)
            try:
                async with page.expect_download(timeout=20000) as download_info:
                    await page.click(used_selector)
                    export_clicked = True
                download = await download_info.value
                await download.save_as(DOWNLOAD_PATH)
                print("Fichier telecharge: " + DOWNLOAD_PATH)
            except Exception as e:
                print("Echec telechargement: " + str(e))
                rows = []
                export_clicked = False

            if export_clicked and os.path.exists(DOWNLOAD_PATH):
                print("[6/6] Lecture du fichier Excel telecharge")
                try:
                    import pandas as pd
                    df = pd.read_excel(DOWNLOAD_PATH)
                    df.columns = [str(c).strip() for c in df.columns]
                    print("Colonnes detectees: " + str(df.columns.tolist()))
                    print("Nb lignes: " + str(len(df)))

                    rows = []
                    for _, r in df.iterrows():
                        rows.append({
                            "statut": statut_from_text(r.get("Statut", "")),
                            "dateExpedition": str(r.get("Date d'expédition", "") or ""),
                            "recepisse": str(r.get("Récépissé", "") or ""),
                            "votreReference": str(r.get("Votre référence", "") or ""),
                            "dateLivraison": str(r.get("Date de livraison", "") or ""),
                            "destinataire": str(r.get("Destinataire", "") or ""),
                            "pays": str(r.get("Pays", "") or ""),
                            "dept": str(r.get("Dépt", "") or ""),
                            "ville": str(r.get("Ville de destination", "") or ""),
                            "poids": str(r.get("Poids", "") or ""),
                            "nbColis": str(r.get("Nb colis", "") or ""),
                        })
                except Exception as e:
                    print("Erreur lecture Excel: " + str(e))
                    rows = []
            else:
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
