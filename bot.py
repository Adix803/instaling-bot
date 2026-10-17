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

# Zmienione na 14-18, żeby zawsze był mały bufor na niechcące błędy
POPRAWNE_ZA_PIERWSZYM = random.randint(14, 18)
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


def popraw_format(tekst, hint):
    """Poprawia wielkość liter i usuwa kropki, żeby pasowało do Instaling."""
    if not tekst:
        return tekst
    tekst = tekst.strip().rstrip('.')
    
    # Jeśli polskie słowo zaczyna się z małej litery, angielskie też powinno
    if hint and hint[0].islower():
        return tekst.lower()
    # Jeśli polskie z dużej, angielskie też (np. Walentynki -> Valentine's Day)
    return tekst[0].upper() + tekst[1:]


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


def answer_widoczne(driver):
    try:
        els = driver.find_elements(By.ID, "answer")
        for el in els:
            if el.is_displayed():
                return True
    except Exception:
        pass
    return False


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
        except Exception:
            time.sleep(2)
    try:
        pole = driver.find_element(By.ID, "answer")
        driver.execute_script("arguments[0].value = arguments[1];", pole, tekst)
        return True
    except Exception:
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

    losowe_opoznienie = 0  # TEST
    print(f"Bot startuje za {losowe_opoznienie} sekund...", flush=True)
    print(f"Plan: {POPRAWNE_ZA_PIERWSZYM} poprawnych, {DOCELOWA_LICZBA_BLEDOW} błędów", flush=True)
    time.sleep(losowe_opoznienie)

    trudne = wczytaj_json(TRUDNE_FILE)
    nauczone = wczytaj_json(NAUCZONE_FILE)

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)

    do_powtorzenia = {}  # hint -> "case" / "typo"
    ocenione = {}
    proby_na_slowo = {}
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

        # --- Start sesji ---
        for proba in range(15):
            if answer_widoczne(driver):
                break
            try:
                btns = driver.find_elements(By.CSS_SELECTOR, ".btn-start-session")
                widoczne = [b for b in btns if b.is_displayed()]
                for btn in widoczne:
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                    time.sleep(1)
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(random.uniform(3, 5))
                    break
            except Exception:
                time.sleep(5)

        if not answer_widoczne(driver):
            print("Pole answer nie pojawiło się.", flush=True)
            return

        # --- Pętla ---
        maks_proby = 100
        poprzednie_pytanie = ""

        for i in range(maks_proby):
            if licznik_poprawnych >= POPRAWNE_ZA_PIERWSZYM and liczba_bledow >= DOCELOWA_LICZBA_BLEDOW:
                print("Osiągnięto oba plany. Kończę.", flush=True)
                break

            for _ in range(20):
                obecne = get_text_js(driver, By.ID, "question")
                if obecne and obecne != poprzednie_pytanie:
                    break
                time.sleep(1)

            pytanie = get_text_js(driver, By.ID, "question")
            hint = get_text_js(driver, By.ID, "question_translation")
            poprzednie_pytanie = pytanie

            if not hint:
                continue

            print(f"\n[{i+1}] PL: '{hint}' | EN: '{pytanie[:50]}'", flush=True)
            print(f"     Postęp: popr={licznik_poprawnych}/{POPRAWNE_ZA_PIERWSZYM}, bł={liczba_bledow}/{DOCELOWA_LICZBA_BLEDOW}", flush=True)

            proby_na_slowo[hint] = proby_na_slowo.get(hint, 0) + 1
            zbyt_wiele_prob = proby_na_slowo[hint] > 4

            juz_ocenione = hint in ocenione
            znam_zdanie = pytanie in nauczone
            mam_trudne = hint in trudne

            # --- Wybór odpowiedzi ---
            if zbyt_wiele_prob:
                odp = trudne.get(hint) or nauczone.get(pytanie) or popraw_format(tlumacz(hint), hint)
                print(f"     Wymuszona: {odp}", flush=True)
            elif znam_zdanie:
                odp = nauczone[pytanie]
                print(f"     Znam zdanie: {odp}", flush=True)
            elif juz_ocenione and mam_trudne:
                odp = trudne[hint]
                print(f"     Zapisana (ocenione): {odp}", flush=True)
            elif juz_ocenione:
                odp = popraw_format(tlumacz(hint), hint)
                print(f"     Już ocenione – poprawiam: {odp}", flush=True)
            elif hint in do_powtorzenia:
                baza = popraw_format(tlumacz(hint), hint)
                if do_powtorzenia[hint] == "case":
                    # Zmień wielkość liter
                    odp = baza.lower() if baza[0].isupper() else baza.capitalize()
                    print(f"     Powtórka (wielkość liter): {odp}", flush=True)
                else:
                    # Literówka / synonim
                    odp = zrob_blad(baza.lower())
                    print(f"     Literówka #2: {odp}", flush=True)
                del do_powtorzenia[hint]
            elif mam_trudne:
                odp = trudne[hint]
                print(f"     Zapisana trudna: {odp}", flush=True)
            else:
                akcja = wybierz_akcje(licznik_poprawnych, liczba_bledow)
                time.sleep(random.uniform(2, 6))
                if akcja == "poprawna":
                    odp = popraw_format(tlumacz(hint), hint)
                    odp = dopasuj_do_zdania(odp, pytanie)
                    print(f"     Tłumaczenie: {odp}", flush=True)
                else:
                    baza = popraw_format(tlumacz(hint), hint)
                    odp = zrob_blad(baza.lower())
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
            print(f"     Status: '{status}'", flush=True)

            poprawna_ze_statusu = wyciagnij_poprawna(status)

            if poprawna_ze_statusu:
                if hint:
                    trudne[hint] = poprawna_ze_statusu
                if pytanie:
                    nauczone[pytanie] = poprawna_ze_statusu
                zapisz_json(TRUDNE_FILE, trudne)
                zapisz_json(NAUCZONE_FILE, nauczone)

            status_lower = status.lower()

            if "dobrze" in status_lower:
                if not juz_ocenione:
                    ocenione[hint] = "correct"
                    licznik_poprawnych += 1
                    print(f"     >>> DOBRZE. Popr: {licznik_poprawnych}", flush=True)
                proby_na_slowo[hint] = 0

            elif "niepoprawnie" in status_lower or "źle" in status_lower:
                if not juz_ocenione:
                    ocenione[hint] = "wrong"
                    liczba_bledow += 1
                    print(f"     >>> BŁĄD. Błędów: {liczba_bledow}", flush=True)

            elif "wielkość liter" in status_lower or "wielkosc" in status_lower:
                if hint and not juz_ocenione:
                    do_powtorzenia[hint] = "case"
                    print(f"     Zła wielkość liter – wróci.", flush=True)

            elif "literówka" in status_lower or "synonim" in status_lower:
                if hint and not juz_ocenione:
                    do_powtorzenia[hint] = "typo"
                    print(f"     Literówka/Synonim – wróci.", flush=True)

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
            time.sleep(random.uniform(1, 3))

        print(f"\nKONIEC. Poprawnych: {licznik_poprawnych}, błędów: {liczba_bledow}", flush=True)

    except Exception as e:
        print(f"Błąd: {e}", flush=True)
        raise
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
