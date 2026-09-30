import os
import json
import requests
from google import genai


# =========================================================
# CONFIGURATION
# =========================================================

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]

MODEL_NAME = "gemini-3.8-flash"

HISTORY_FILE = "history.json"

MAX_HISTORY = 3650


# =========================================================
# LOAD HISTORY
# =========================================================

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, list):
            return data

        return []

    except (json.JSONDecodeError, OSError):
        return []


# =========================================================
# SAVE HISTORY
# =========================================================

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as file:
        json.dump(
            history,
            file,
            ensure_ascii=False,
            indent=2
        )


# =========================================================
# GENERATE MESSAGE
# =========================================================

def generate_message(history):

    # Kirim sebagian history agar prompt tidak terlalu besar
    recent_history = history[-200:]

    history_text = "\n".join(
        f"- {message}"
        for message in recent_history
    )

    if not history_text:
        history_text = "(Belum ada pesan sebelumnya)"

    prompt = f"""
Buat SATU daily reminder romantis dalam Bahasa Indonesia
untuk pasangan.

Tujuan:
- Hangat
- Cute
- Natural
- Tidak terlalu formal
- Tidak berlebihan
- Cocok dikirim setiap pagi
- Bisa berupa pengingat sederhana untuk saling menyayangi,
  menjaga diri, semangat menjalani hari, makan, istirahat,
  menghargai pasangan, atau bersyukur.

Aturan:
1. Hanya buat SATU pesan.
2. Panjang sekitar 1-3 kalimat.
3. Gunakan Bahasa Indonesia yang natural dan santai.
4. Boleh menggunakan emoji.
5. Jangan selalu menggunakan kata "sayang".
6. Jangan selalu diawali dengan "Selamat pagi".
7. Jangan menggunakan struktur kalimat yang sama berulang kali.
9. Jangan menyebut bahwa pesan dibuat oleh AI.
10. Pesan harus terasa seperti reminder kecil yang manis.
11. Jangan menyalin pesan yang ada di history.
12. Buat pesan yang berbeda dari pesan-pesan sebelumnya.

Berikut history pesan yang SUDAH PERNAH digunakan:

{history_text}

Sekarang buat satu pesan baru yang berbeda.

Output HANYA pesan reminder-nya.
Jangan gunakan tanda kutip.
Jangan tambahkan penjelasan.
"""

    client = genai.Client(api_key=GEMINI_API_KEY)

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )

    message = response.text.strip()

    return message


# =========================================================
# CHECK DUPLICATE
# =========================================================

def is_duplicate(message, history):

    normalized_message = " ".join(
        message.lower().split()
    )

    for old_message in history:

        normalized_old = " ".join(
            old_message.lower().split()
        )

        if normalized_message == normalized_old:
            return True

    return False


# =========================================================
# SEND TO DISCORD
# =========================================================

def send_to_discord(message):

    payload = {
        "content": message,
        "username": "Daily Reminder 💌"
    }

    response = requests.post(
        DISCORD_WEBHOOK_URL,
        json=payload,
        timeout=30
    )

    if response.status_code not in (200, 204):
        raise Exception(
            f"Discord webhook error: "
            f"{response.status_code} - {response.text}"
        )


# =========================================================
# MAIN
# =========================================================

def main():

    print("===================================")
    print("💌 DAILY REMINDER BOT")
    print("===================================")

    history = load_history()

    print(f"History loaded: {len(history)} messages")

    # =====================================================
    # Generate message
    # =====================================================

    max_attempts = 3

    for attempt in range(max_attempts):

        print(
            f"Generating message "
            f"(attempt {attempt + 1}/{max_attempts})..."
        )

        message = generate_message(history)

        print("Generated:")
        print(message)

        if not is_duplicate(message, history):
            break

        print("Duplicate detected. Generating again...")

    else:
        raise Exception(
            "Failed to generate a unique message."
        )

    # =====================================================
    # Send Discord
    # =====================================================

    print("Sending message to Discord...")

    send_to_discord(message)

    print("Message sent successfully! 💌")

    # =====================================================
    # Save history
    # =====================================================

    history.append(message)

    # Batasi ukuran history
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]

    save_history(history)

    print(
        f"History saved: {len(history)} messages"
    )

    print("===================================")
    print("DONE ❤️")
    print("===================================")


if __name__ == "__main__":
    main()