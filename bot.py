import os
import json
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

POPRAWNE_ZA_PIERWSZYM = random.randint(10, 17)
DOCELOWA_LICZBA_BLEDOW = 20 - POPRAWNE_ZA_PIERWSZYM


def wczytaj_trudne():
    if os.path.exists(TRUDNE_FILE):
        try:
            with open(TRUDNE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def zapisz_trudne(dane):
    with open(TRUDNE_FILE, "w", encoding="utf-8") as f:
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
        return r.json()["responseData"]["translatedText"].strip()
    except Exception as e:
        print(f"Błąd tłumaczenia: {e}")
        return tekst


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
            print(f"     Próba {proba+1} wpisania nie udała się: {e}")
            time.sleep(2)
    try:
        pole = driver.find_element(By.ID, "answer")
        driver.execute_script("arguments[0].value = arguments[1];", pole, tekst)
        return True
    except Exception as e:
        print(f"     JS fallback też nie zadziałał: {e}")
        return False


def wybierz_akcje(licznik_poprawnych, liczba_bledow):
    """Losowo decyduje, czy kolejne słowo ma być poprawne, czy błędne.
    Uwzględnia ile jeszcze zostało do wykonania."""
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
        print("Bot wyłączony – minęła data 2027-06-01.")
        return

    losowe_opoznienie = 0  # TEST – potem zmień na random.randint(0, 6 * 3600)
    print(f"Bot startuje za {losowe_opoznienie} sekund...")
    print(f"Plan: {POPRAWNE_ZA_PIERWSZYM} poprawnych, {DOCELOWA_LICZBA_BLEDOW} błędów (rozrzucone losowo)")
    time.sleep(losowe_opoznienie)

    trudne = wczytaj_trudne()

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)

    do_powtorzenia = {}
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
        print(f"Po logowaniu: {driver.current_url}")

        # --- Start / Kontynuacja sesji ---
        try:
            btn = WebDriverWait(driver, 20).until(EC.element_to_be_clickable(
                (By.XPATH,
                 "//button[contains(text(), 'Rozpocznij sesję')] | //a[contains(text(), 'Dokończ sesję')] | //button[contains(text(), 'Dokończ sesję')]")))
            btn.click()
            print("Kliknięto Rozpocznij/Dokończ sesję.")
            time.sleep(random.uniform(3, 5))
        except Exception as e:
            print(f"Nie znaleziono przycisku startu: {e}")
            return

        # --- "Kontynuuj sesję" (jeśli jest) ---
        try:
            btn2 = WebDriverWait(driver, 8).until(EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(text(), 'Kontynuuj sesję')]")))
            btn2.click()
            print("Kliknięto 'Kontynuuj sesję'.")
            time.sleep(random.uniform(3, 5))
        except Exception:
            print("Brak 'Kontynuuj sesję' – idę dalej.")

        # --- Czekaj na pole answer ---
        try:
            WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "answer")))
            print("Pole 'answer' znalezione.")
        except Exception:
            print("Pole 'answer' się nie pojawiło.")
            return

        # --- Pętla ---
        maks_proby = 300
        poprzednie_pytanie = ""

        for i in range(maks_proby):
            # czekaj na nowe pytanie
            for _ in range(15):
                obecne = get_text_js(driver, By.ID, "question")
                if obecne and obecne != poprzednie_pytanie:
                    break
                time.sleep(1)

            pytanie = get_text_js(driver, By.ID, "question")
            hint = get_text_js(driver, By.ID, "question_translation")
            poprzednie_pytanie = pytanie

            print(f"[{i+1}] PL: '{hint}' | EN: '{pytanie[:80]}'")
            print(f"     Postęp: poprawnych={licznik_poprawnych}/{POPRAWNE_ZA_PIERWSZYM}, błędów={liczba_bledow}/{DOCELOWA_LICZBA_BLEDOW}")

            if not hint:
                print("     Pusty hint – pomijam.")
                continue

            # --- Wybierz co robimy z tym słowem ---
            if hint in do_powtorzenia:
                akcja = "blad_2"
            elif hint in trudne:
                akcja = "poprawna_zapisana"
            else:
                akcja = wybierz_akcje(licznik_poprawnych, liczba_bledow)

            time.sleep(random.uniform(3, 12))

            if akcja == "blad_2":
                odp = zrob_blad(tlumacz(hint))
                print(f"     Literówka #2 (ma być błąd): {odp}")
                del do_powtorzenia[hint]
            elif akcja == "poprawna_zapisana":
                odp = trudne[hint]
                print(f"     Zapisana poprawna: {odp}")
            elif akcja == "poprawna":
                odp = tlumacz(hint)
                print(f"     Tłumaczenie (poprawna): {odp}")
            else:  # "blad" – pierwsza literówka
                odp = zrob_blad(tlumacz(hint))
                print(f"     Literówka #1 (żeby wróciło): {odp}")

            if not wpisz_odpowiedz(driver, odp):
                print("     Nie udało się wpisać – przerywam.")
                break

            time.sleep(random.uniform(1, 2))

            # kliknij Sprawdź
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
            print(f"     Status: {status}")

            if "Dobrze" in status:
                licznik_poprawnych += 1
                print(f"     >>> Dobrze. Razem poprawnych: {licznik_poprawnych}")
            elif "Niepoprawnie" in status:
                liczba_bledow += 1
                try:
                    el = driver.find_element(By.CSS_SELECTOR, "#answer_result strong, #answer_result b")
                    poprawna = driver.execute_script("return arguments[0].textContent", el).strip()
                except Exception:
                    poprawna = ""
                if poprawna and hint:
                    trudne[hint] = poprawna
                    zapisz_trudne(trudne)
                    print(f"     Zapisano: {hint} -> {poprawna}")
                print(f"     >>> Błąd zaliczony. Razem błędów: {liczba_bledow}")
            elif "Literówka" in status or "Synonim" in status:
                if hint:
                    do_powtorzenia[hint] = True
                    print(f"     Literówka/synonim – zapamiętane (wróci źle jeszcze raz).")

            # kliknij Dalej / Następne
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

        print(f"Koniec sesji. Poprawnych: {licznik_poprawnych}, błędów: {liczba_bledow}")

    except Exception as e:
        print(f"Błąd: {e}")
        raise
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
