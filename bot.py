import os
import random
import time
from instaling_client import InstalingClient

# Pobierz dane logowania z GitHub Secrets
EMAIL = os.environ.get("INSTALING_EMAIL")
PASSWORD = os.environ.get("INSTALING_PASSWORD")

# --- KONFIGURACJA ---
# Losujemy, ile słówek ma być poprawnych za pierwszym razem (od 10 do 17)
POPRAWNE_ZA_PIERWSZYM = random.randint(10, 17)

def zrob_blad(slowo):
    """Zwraca słowo z symulowanym, ludzkim błędem."""
    opcje = [
        # Zamiana dwóch sąsiednich liter (np. "recieve" -> "receive")
        lambda s: s[:-1] + s[-2] + s[-1] if len(s) > 2 else s + "x",
        # Opuszczenie jednej litery (np. "beautiful" -> "beutiful")
        lambda s: s[:len(s)//2] + s[len(s)//2+1:] if len(s) > 3 else s,
        # Podwojenie litery (np. "necessary" -> "neccessary")
        lambda s: s.replace("c", "cc", 1) if "c" in s else s + s[-1],
        # Typowa pomyłka "ie" -> "ei"
        lambda s: s.replace("ie", "ei") if "ie" in s else s,
    ]
    return random.choice(opcje)(slowo)

def main():
    # --- LOSOWE OPÓŹNIENIE STARTU (po 17:30) ---
    # Cron ustawimy na 17:30 UTC. Dodatkowe opóźnienie (0-4h) sprawi,
    # że bot wystartuje między 17:30 a 21:30, co wygląda naturalnie.
    losowe_opoznienie = random.randint(0, 4 * 3600)  # 0-4 godziny w sekundach
    print(f"Bot startuje za {losowe_opoznienie} sekund...")
    time.sleep(losowe_opoznienie)

    client = InstalingClient()
    try:
        client.login(EMAIL, PASSWORD)
    except Exception as e:
        print(f"Błąd logowania: {e}")
        return

    if client.session_completed:
        print("Sesja na dziś jest już ukończona.")
        return

    print("Rozpoczynam dzisiejszą sesję...")

    # Pobierz listę słówek. Nazwa metody może być inna – sprawdź w dokumentacji.
    words = client.get_words()
    licznik_poprawnych = 0

    for word in words:
        # Ludzkie opóźnienie między odpowiedziami
        time.sleep(random.uniform(3, 12))

        if licznik_poprawnych < POPRAWNE_ZA_PIERWSZYM:
            # Odpowiedz poprawnie
            client.answer(word, word['poprawna_odpowiedz'])
            licznik_poprawnych += 1
        else:
            # Odpowiedz z błędem
            bledna_odpowiedz = zrob_blad(word['poprawna_odpowiedz'])
            client.answer(word, bledna_odpowiedz)

    # Po zakończeniu pierwszej rundy bot powinien poprawić błędy.
    # Niektóre biblioteki robią to automatycznie, inne wymagają wywołania.
    try:
        client.finish_session()
    except AttributeError:
        pass

    print("Sesja zakończona.")

if __name__ == "__main__":
    main()
  



