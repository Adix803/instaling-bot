import os
import json
import re
import random
import time
from datetime import date
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

EMAIL = os.environ.get("INSTALING_EMAIL")
PASSWORD = os.environ.get("INSTALING_PASSWORD")
TRUDNE_FILE = "trudne.json"
NAUCZONE_FILE = "nauczone.json"

POPRAWNE_ZA_PIERWSZYM = random.randint(14, 20)
DOCELOWA_LICZBA_BLEDOW = 20 - POPRAWNE_ZA_PIERWSZYM


def wczytaj_json(plik):
    if os.path.exists(plik):
        try:
            with open(plik, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def zapisz_json(plik, dane):
    with open(plik, "w", encoding="utf-8") as f:
        json.dump(dane, f, ensure_ascii=False, indent=2)


def tlumacz(tekst):
    if not tekst:
        return ""
    try:
        r = requests.get(
            "https://api.mymemory.translated.net/get",
            params={"q": tekst, "langpair": "pl|en"},
            timeout=10,
        )
        wynik = r.json()["responseData"]["translatedText"].strip()
        if wynik and "NO QUERY" not in wynik.upper():
            return wynik
    except Exception:
        pass
    try:
        r = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "pl", "tl": "en", "dt": "t", "q": tekst},
            timeout=10,
        )
        return r.json()[0][0][0].strip()
    except Exception as e:
        print(f"Błąd tłumaczenia: {e}", flush=True)
        return tekst


def dopasuj_do_zdania(odp, pytanie):
    if not odp or not pytanie:
        return odp

    if "___" in pytanie:
        przed = pytanie.split("___")[0].strip().lower()
        slowa_przed = przed.split()
        ostatnie = slowa_przed[-1] if slowa_przed else ""
        if ostatnie in ("the", "a", "an"):
            for art in ("the ", "a ", "an "):
                if odp.lower().startswith(art):
                    odp = odp[len(art):].strip()
                    break
        if " the " in f" {przed} " or " a " in f" {przed} " or " an " in f" {przed} ":
            slowa_odp = odp.split()
            if len(slowa_odp) >= 2 and slowa_odp[0].lower() in ("the", "a", "an"):
                odp = " ".join(slowa_odp[1:])

    if "___" in pytanie:
        przed = pytanie.split("___")[0].lower()
        mnogie = ["some", "many", "few", "these", "those", "several", "two", "three", "a lot of"]
        po = pytanie.split("___")[1].lower() if len(pytanie.split("___")) > 1 else ""
        sugeruje_mnogą = any(m in przed.split() for m in mnogie) or po.strip().startswith("are")

        if sugeruje_mnogą and odp and not odp.endswith("s"):
            if odp.endswith("y"):
                odp_mnoga = odp[:-1] + "ies"
            elif odp.endswith(("s", "sh", "ch", "x", "z")):
                odp_mnoga = odp + "es"
            else:
                odp_mnoga = odp + "s"
            print(f"     (zdanie sugeruje mnogą: '{odp}' -> '{odp_mnoga}')", flush=True)
            odp = odp_mnoga

    return odp


def zrob_blad(slowo):
    if not slowo:
        return "x"
    opcje = [
        lambda s: s[:-1] + s[-2] + s[-1] if len(s) > 2 else s + "x",
        lambda s: s[:len(s)//2] + s[len(s)//2+1:] if len(s) > 3 else s,
        lambda s: s.replace("c", "cc", 1) if "c" in s else s + s[-1],
        lambda s: s.replace("ie", "ei") if "ie" in s else s,
    ]
    return random.choice(opcje)(slowo)


def get_text_js(driver, by, selector):
    try:
        el = driver.find_element(by, selector)
        return driver.execute_script("return arguments[0].textContent", el).strip()
    except Exception:
        return ""


def wyciagnij_poprawna(status_text):
    if not status_text:
        return ""
    m = re.search(r"Poprawna odpowied[źz]?:?\s*(.+)", status_text, re.IGNORECASE)
    if m:
        return m.group(1).split("\n")[0].strip()
    return ""


def wpisz_odpowiedz(driver, tekst):
    for proba in range(3):
        try:
            pole = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.ID, "answer"))
            )
            if pole.get_attribute("disabled"):
                time.sleep(1)
                continue
            pole.click()
            pole.clear()
            time.sleep(0.3)
            pole.send_keys(tekst)
            return True
        except Exception as e:
            print(f"     Próba {proba+1} wpisania: {e}", flush=True)
            time.sleep(2)
    try:
        pole = driver.find_element(By.ID, "answer")
        driver.execute_script("arguments[0].value = arguments[1];", pole, tekst)
        return True
    except Exception as e:
        print(f"     JS fallback: {e}", flush=True)
        return False


def wybierz_akcje(licznik_poprawnych, liczba_bledow):
    pozostalo_poprawnych = POPRAWNE_ZA_PIERWSZYM - licznik_poprawnych
    pozostalo_bledow = DOCELOWA_LICZBA_BLEDOW - liczba_bledow
    if pozostalo_bledow <= 0:
        return "poprawna"
    if pozostalo_poprawnych <= 0:
        return "blad"
    total = pozostalo_poprawnych + pozostalo_bledow
    if random.random() < pozostalo_poprawnych / total:
        return "poprawna"
    return "blad"


def main():
    if date.today() >= date(2027, 6, 1):
        print("Bot wyłączony – minęła data 2027-06-01.", flush=True)
        return

    losowe_opoznienie = random.randint(0, 9000)  # 0-2.5h -> 17:30-20:00 PL zimą
    print(f"Bot startuje za {losowe_opoznienie} sekund...", flush=True)
    print(f"Plan: {POPRAWNE_ZA_PIERWSZYM} poprawnych, {DOCELOWA_LICZBA_BLEDOW} błędów", flush=True)
    time.sleep(losowe_opoznienie)

    trudne = wczytaj_json(TRUDNE_FILE)
    nauczone = wczytaj_json(NAUCZONE_FILE)
    print(f"Załadowano {len(trudne)} słów i {len(nauczone)} zdań", flush=True)

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)

    do_powtorzenia = {}
    ocenione = {}
    liczba_bledow = 0
    licznik_poprawnych = 0

    try:
        # --- Logowanie ---
        driver.get("https://instaling.pl/teacher.php?page=login")
        time.sleep(random.uniform(2, 4))
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.NAME, "log_email"))
        ).send_keys(EMAIL)
        time.sleep(random.uniform(1, 2))
        driver.find_element(By.NAME, "log_password").send_keys(PASSWORD)
        time.sleep(random.uniform(1, 2))
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        time.sleep(random.uniform(3, 5))
        print(f"Po logowaniu: {driver.current_url}", flush=True)

        # --- Start / Kontynuacja ---
        try:
            btn = WebDriverWait(driver, 20).until(EC.element_to_be_clickable(
                (By.XPATH,
                 "//button[contains(text(), 'Rozpocznij sesję')] | //a[contains(text(), 'Dokończ sesję')] | //button[contains(text(), 'Dokończ sesję')]")))
            btn.click()
            print("Kliknięto start sesji.", flush=True)
            time.sleep(random.uniform(3, 5))
        except Exception as e:
            print(f"Nie znaleziono przycisku startu: {e}", flush=True)
            return

        try:
            btn2 = WebDriverWait(driver, 8).until(EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(text(), 'Kontynuuj sesję')]")))
            btn2.click()
            print("Kliknięto 'Kontynuuj sesję'.", flush=True)
            time.sleep(random.uniform(3, 5))
        except Exception:
            pass

        try:
            WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "answer")))
            print("Pole 'answer' znalezione.", flush=True)
        except Exception:
            print("Pole 'answer' się nie pojawiło.", flush=True)
            return

        # --- Pętla ---
        maks_proby = 300
        poprzednie_pytanie = ""

        for i in range(maks_proby):
            for _ in range(15):
                obecne = get_text_js(driver, By.ID, "question")
                if obecne and obecne != poprzednie_pytanie:
                    break
                time.sleep(1)

            pytanie = get_text_js(driver, By.ID, "question")
            hint = get_text_js(driver, By.ID, "question_translation")
            poprzednie_pytanie = pytanie

            print(f"\n[{i+1}] PL: '{hint}' | EN: '{pytanie[:80]}'", flush=True)
            print(f"     Postęp: poprawnych={licznik_poprawnych}/{POPRAWNE_ZA_PIERWSZYM}, błędów={liczba_bledow}/{DOCELOWA_LICZBA_BLEDOW}", flush=True)

            if not hint:
                print("     Pusty hint – pomijam.", flush=True)
                continue

            juz_ocenione = hint in ocenione
            znam_zdanie = pytanie in nauczone

            if juz_ocenione:
                akcja = "poprawna_bez_liczenia"
            elif znam_zdanie:
                akcja = "poprawna_z_zdania"
            elif hint in do_powtorzenia:
                akcja = "blad_2"
            elif hint in trudne:
                akcja = "poprawna_zapisana"
            else:
                akcja = wybierz_akcje(licznik_poprawnych, liczba_bledow)

            time.sleep(random.uniform(3, 12))

            if akcja == "poprawna_bez_liczenia":
                odp = nauczone.get(pytanie) or trudne.get(hint) or tlumacz(hint)
                odp = dopasuj_do_zdania(odp, pytanie)
                print(f"     Już ocenione – poprawiam: {odp}", flush=True)
            elif akcja == "poprawna_z_zdania":
                odp = nauczone[pytanie]
                print(f"     Znam to zdanie! Użyję zapisanej: {odp}", flush=True)
            elif akcja == "blad_2":
                odp = zrob_blad(tlumacz(hint))
                print(f"     Literówka #2: {odp}", flush=True)
                del do_powtorzenia[hint]
            elif akcja == "poprawna_zapisana":
                odp = dopasuj_do_zdania(trudne[hint], pytanie)
                print(f"     Zapisana poprawna: {odp}", flush=True)
            elif akcja == "poprawna":
                odp = tlumacz(hint)
                odp = dopasuj_do_zdania(odp, pytanie)
                print(f"     Tłumaczenie (poprawna): {odp}", flush=True)
            else:
                odp = zrob_blad(tlumacz(hint))
                print(f"     Literówka #1: {odp}", flush=True)

            if not wpisz_odpowiedz(driver, odp):
                break

            time.sleep(random.uniform(1, 2))

            try:
                driver.find_element(By.XPATH, "//button[contains(text(), 'Sprawdź')]").click()
            except Exception:
                try:
                    btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Sprawdź')]")
                    driver.execute_script("arguments[0].click();", btn)
                except Exception:
                    break

            time.sleep(random.uniform(2, 4))

            status = get_text_js(driver, By.ID, "sr_status")
            print(f"     Status: {status}", flush=True)

            poprawna_ze_statusu = wyciagnij_poprawna(status)

            if poprawna_ze_statusu and pytanie:
                nauczone[pytanie] = poprawna_ze_statusu
                zapisz_json(NAUCZONE_FILE, nauczone)
                print(f"     Zapisano zdanie: {pytanie[:50]}... -> {poprawna_ze_statusu}", flush=True)

            if "Dobrze" in status:
                if not juz_ocenione:
                    ocenione[hint] = "correct"
                    licznik_poprawnych += 1
                    print(f"     >>> DOBRZE. Poprawnych: {licznik_poprawnych}", flush=True)
                else:
                    print(f"     >>> Dobrze (powtórka)", flush=True)

            elif "Niepoprawnie" in status:
                if not juz_ocenione:
                    ocenione[hint] = "wrong"
                    liczba_bledow += 1
                    print(f"     >>> BŁĄD. Błędów: {liczba_bledow}", flush=True)
                else:
                    print(f"     >>> Niepoprawnie (powtórka)", flush=True)

                if poprawna_ze_statusu and hint and poprawna_ze_statusu.lower() != odp.lower():
                    trudne[hint] = poprawna_ze_statusu
                    zapisz_json(TRUDNE_FILE, trudne)

            elif "Literówka" in status or "Synonim" in status:
                if hint and not juz_ocenione:
                    do_powtorzenia[hint] = True
                    print(f"     Literówka/synonim – wróci, zrobię źle jeszcze raz.", flush=True)

            time.sleep(random.uniform(1, 2))
            try:
                driver.find_element(By.XPATH,
                    "//button[contains(text(), 'Dalej')] | //button[contains(text(), 'Następne')] | //button[contains(text(), 'Kontynuuj')]").click()
            except Exception:
                try:
                    btn = driver.find_element(By.XPATH,
                        "//button[contains(text(), 'Dalej')] | //button[contains(text(), 'Następne')]")
                    driver.execute_script("arguments[0].click();", btn)
                except Exception:
                    pass

            time.sleep(random.uniform(2, 4))

        print(f"\nKoniec sesji. Poprawnych: {licznik_poprawnych}, błędów: {liczba_bledow}", flush=True)

    except Exception as e:
        print(f"Błąd: {e}", flush=True)
        raise
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
