import os
import json
import time
import requests
from google import genai


# =========================================================
# CONFIG
# =========================================================

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]

HISTORY_FILE = "history.json"
MAX_HISTORY = 3650

# Jumlah percobaan untuk setiap model
MAX_RETRIES_PER_MODEL = 2


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
# GET AVAILABLE GEMINI MODELS
# =========================================================

def get_available_models(client):

    print("Checking available Gemini models...")

    models = []

    try:

        for model in client.models.list():

            model_name = model.name

            # Hanya gunakan model yang mendukung generateContent
            supported_methods = getattr(
                model,
                "supported_actions",
                []
            )

            if (
                "generateContent" in supported_methods
                or not supported_methods
            ):

                models.append(model_name)

    except Exception as error:

        print(f"Failed to list Gemini models: {error}")

    # Hapus duplicate
    models = list(dict.fromkeys(models))

    print("Available models:")

    for model in models:
        print(f" - {model}")

    return models


# =========================================================
# CREATE PROMPT
# =========================================================

def create_prompt(history):

    recent_history = history[-200:]

    history_text = "\n".join(
        f"- {message}"
        for message in recent_history
    )

    if not history_text:
        history_text = "(Belum ada pesan sebelumnya)"

    return f"""
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
4. Boleh menggunakan emoji, tetapi jangan berlebihan.
5. Jangan selalu menggunakan kata "sayang".
6. Jangan selalu diawali dengan "Selamat pagi".
7. Jangan menggunakan struktur kalimat yang sama berulang kali.
8. Jangan membuat pesan terlalu cheesy.
9. Jangan menyebut bahwa pesan dibuat oleh AI.
10. Pesan harus terasa seperti reminder kecil yang manis.
11. Jangan menyalin pesan yang ada di history.
12. Buat pesan yang berbeda dari pesan-pesan sebelumnya.

History pesan yang sudah pernah digunakan:

{history_text}

Buat SATU pesan baru yang berbeda.

Output HANYA pesan reminder-nya.
Jangan gunakan tanda kutip.
Jangan tambahkan penjelasan.
"""


# =========================================================
# GENERATE MESSAGE WITH MODEL FALLBACK
# =========================================================

def generate_message(client, history):

    prompt = create_prompt(history)

    models = get_available_models(client)

    if not models:
        raise Exception(
            "Tidak ada Gemini model yang tersedia."
        )

    # =====================================================
    # Prioritas model
    # =====================================================

    # Model yang mengandung "flash" biasanya lebih cocok
    # untuk tugas ringan seperti daily reminder.
    flash_models = [
        model for model in models
        if "flash" in model.lower()
    ]

    other_models = [
        model for model in models
        if model not in flash_models
    ]

    models = flash_models + other_models

    print("\nModel fallback order:")

    for index, model in enumerate(models, start=1):
        print(f"{index}. {model}")

    # =====================================================
    # Coba setiap model
    # =====================================================

    for model_name in models:

        print(
            f"\nTrying model: {model_name}"
        )

        for attempt in range(MAX_RETRIES_PER_MODEL):

            try:

                print(
                    f"Attempt "
                    f"{attempt + 1}/"
                    f"{MAX_RETRIES_PER_MODEL}"
                )

                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )

                message = response.text.strip()

                if not message:
                    raise Exception(
                        "Model returned empty response."
                    )

                print(
                    f"SUCCESS using {model_name}"
                )

                return message

            except Exception as error:

                error_text = str(error)

                print(
                    f"Error from {model_name}:"
                )

                print(error_text)

                # =========================================
                # Temporary error
                # =========================================

                temporary_error = (
                    "503" in error_text
                    or "UNAVAILABLE" in error_text
                    or "429" in error_text
                    or "RESOURCE_EXHAUSTED" in error_text
                    or "500" in error_text
                )

                if temporary_error:

                    if attempt < MAX_RETRIES_PER_MODEL - 1:

                        wait_time = 10 * (attempt + 1)

                        print(
                            f"Temporary error."
                            f" Waiting {wait_time} seconds..."
                        )

                        time.sleep(wait_time)

                    else:

                        print(
                            f"{model_name} failed."
                            f" Moving to next model..."
                        )

                else:

                    print(
                        f"Non-temporary error."
                        f" Moving to next model..."
                    )

                    break

    # Semua model gagal
    raise Exception(
        "All available Gemini models failed."
    )


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
        "content": message
    }

    response = requests.post(
        DISCORD_WEBHOOK_URL,
        json=payload,
        timeout=30
    )

    if response.status_code not in (200, 204):

        raise Exception(
            f"Discord webhook error: "
            f"{response.status_code} - "
            f"{response.text}"
        )


# =========================================================
# MAIN
# =========================================================

def main():

    print("======================================")
    print("💌 DAILY ROMANTIC REMINDER")
    print("======================================")

    history = load_history()

    print(
        f"History loaded: "
        f"{len(history)} messages"
    )

    client = genai.Client(
        api_key=GEMINI_API_KEY
    )

    # =====================================================
    # Generate message
    # =====================================================

    max_duplicate_attempts = 3

    for attempt in range(max_duplicate_attempts):

        print(
            f"\nGenerating message "
            f"({attempt + 1}/"
            f"{max_duplicate_attempts})..."
        )

        message = generate_message(
            client,
            history
        )

        print("\nGenerated message:")
        print(message)

        if not is_duplicate(message, history):

            break

        print(
            "Duplicate detected."
            " Generating another message..."
        )

    else:

        raise Exception(
            "Failed to generate unique message."
        )

    # =====================================================
    # Send Discord
    # =====================================================

    print("\nSending to Discord...")

    send_to_discord(message)

    print(
        "Discord message sent successfully! 💌"
    )

    # =====================================================
    # Save history
    # =====================================================

    history.append(message)

    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]

    save_history(history)

    print(
        f"History saved."
        f" Total messages: {len(history)}"
    )

    print("\n======================================")
    print("DONE ❤️")
    print("======================================")


if __name__ == "__main__":
    main()