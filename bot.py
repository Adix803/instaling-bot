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
    """Pobiera tekst elementu przez JS (działa nawet jak ukryty)."""
    try:
        el = driver.find_element(by, selector)
        return driver.execute_script("return arguments[0].textContent", el).strip()
    except Exception:
        return ""


def main():
    if date.today() >= date(2027, 6, 1):
        print("Bot wyłączony – minęła data 2027-06-01.")
        return

    losowe_opoznienie = 0  # TEST
    print(f"Bot startuje za {losowe_opoznienie} sekund...")
    time.sleep(losowe_opoznienie)

    trudne = wczytaj_trudne()

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 20)

    do_powtorzenia = {}
    liczba_bledow = 0
    docelowa_liczba_bledow = 20 - POPRAWNE_ZA_PIERWSZYM

    try:
        # --- Logowanie ---
        driver.get("https://instaling.pl/teacher.php?page=login")
        time.sleep(random.uniform(2, 4))
        wait.until(EC.presence_of_element_located((By.NAME, "log_email"))).send_keys(EMAIL)
        time.sleep(random.uniform(1, 2))
        driver.find_element(By.NAME, "log_password").send_keys(PASSWORD)
        time.sleep(random.uniform(1, 2))
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        time.sleep(random.uniform(3, 5))
        print(f"Po logowaniu: {driver.current_url}")

        # --- Start / Kontynuacja sesji ---
        try:
            btn = wait.until(EC.element_to_be_clickable(
                (By.XPATH,
                 "//button[contains(text(), 'Rozpocznij sesję')] | //a[contains(text(), 'Dokończ sesję')] | //button[contains(text(), 'Dokończ sesję')]")))
            btn.click()
            print("Kliknięto start/kontynuację sesji.")
            time.sleep(random.uniform(4, 6))
                    print(f"URL po kliknięciu: {driver.current_url}")
        with open("page_after_start.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("Zapisano page_after_start.html")
        except Exception as e:
            print(f"Nie znaleziono przycisku sesji: {e}")
            print(f"URL: {driver.current_url}")
            return

        # --- Pętla słówek ---
        licznik_poprawnych = 0
        maks_proby = 300

        for i in range(maks_proby):
            # Czekaj aż pole answer się pojawi i będzie interaktywne
            try:
                pole = wait.until(EC.element_to_be_clickable((By.ID, "answer")))
            except Exception:
                print("Koniec sesji – brak pola odpowiedzi.")
                break

            # Pobierz tekst przez JS (działa nawet dla ukrytych)
            pytanie = get_text_js(driver, By.ID, "question")
            hint = get_text_js(driver, By.ID, "question_translation")

            print(f"[{i+1}] PL: '{hint}' | EN: '{pytanie[:80]}'")
            print(f"     Postęp: poprawnych={licznik_poprawnych}, błędów={liczba_bledow}/{docelowa_liczba_bledow}")

            if not hint:
                print("     Pusty hint – pomijam, klikam Sprawdź żeby przejść dalej.")
                # spróbuj kliknąć Sprawdź mimo wszystko
                try:
                    driver.find_element(By.XPATH, "//button[contains(text(), 'Sprawdź')]").click()
                    time.sleep(random.uniform(2, 4))
                    # Dalej
                    try:
                        driver.find_element(By.XPATH,
                            "//button[contains(text(), 'Dalej')] | //button[contains(text(), 'Następne')] | //button[contains(text(), 'Kontynuuj')]").click()
                        time.sleep(random.uniform(1, 3))
                    except Exception:
                        pass
                except Exception:
                    pass
                continue

            powtarzamy = hint in do_powtorzenia
            time.sleep(random.uniform(3, 12))

            if powtarzamy:
                odp = zrob_blad(tlumacz(hint))
                print(f"     Literówka #2 (ma być błąd): {odp}")
                del do_powtorzenia[hint]
            elif hint in trudne:
                odp = trudne[hint]
                print(f"     Zapisana poprawna: {odp}")
            elif licznik_poprawnych < POPRAWNE_ZA_PIERWSZYM:
                odp = tlumacz(hint)
                print(f"     Tłumaczenie: {odp}")
                licznik_poprawnych += 1
            else:
                odp = zrob_blad(tlumacz(hint))
                print(f"     Literówka #1: {odp}")

            # Wpisz odpowiedź – przez JS dla pewności
            try:
                driver.execute_script("arguments[0].value = '';", pole)
                pole.send_keys(odp)
                time.sleep(random.uniform(1, 2))
            except Exception as e:
                print(f"     Nie mogę wpisać: {e}")
                break

            # Sprawdź
            try:
                driver.find_element(By.XPATH, "//button[contains(text(), 'Sprawdź')]").click()
            except Exception as e:
                print(f"Nie znaleziono Sprawdź: {e}")
                break

            time.sleep(random.uniform(2, 4))

            status = get_text_js(driver, By.ID, "sr_status")
            print(f"     Status: {status}")

            if "Niepoprawnie" in status:
                liczba_bledow += 1
                # poprawna odpowiedź z answer_result
                poprawna = ""
                try:
                    el = driver.find_element(By.CSS_SELECTOR, "#answer_result strong, #answer_result b, #answer_result .text-success")
                    poprawna = driver.execute_script("return arguments[0].textContent", el).strip()
                except Exception:
                    pass
                if poprawna and hint:
                    trudne[hint] = poprawna
                    zapisz_trudne(trudne)
                    print(f"     Zapisano: {hint} -> {poprawna}")
                print(f"     >>> Błąd zaliczony. Razem błędów: {liczba_bledow}")

            elif "Literówka" in status or "Synonim" in status:
                if hint:
                    do_powtorzenia[hint] = True
                    print(f"     Literówka/synonim – zapamiętane.")

            # Dalej
            try:
                driver.find_element(By.XPATH,
                    "//button[contains(text(), 'Dalej')] | //button[contains(text(), 'Następne')] | //button[contains(text(), 'Kontynuuj')]").click()
                time.sleep(random.uniform(1, 3))
            except Exception:
                pass

        print(f"Koniec sesji. Poprawnych: {licznik_poprawnych}, błędów: {liczba_bledow}")

    except Exception as e:
        print(f"Błąd: {e}")
        raise
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
