import os
import requests
import gc
import threading
import time
import signal
from flask import Flask, request, jsonify
from googleapiclient.discovery import build

app = Flask(__name__)

# --- EVOLUTION API AYARLARI ---
EVO_URL = "https://evolution-api-awf2.onrender.com"
EVO_API_KEY = "Bosphore2026!"

# --- GOOGLE DRIVE AYARLARI ---
DRIVE_API_KEY = "AIzaSyB2TachWmeBOvuGYUin6V5IVgxqXyWuv8A"
DRIVE_FOLDER_ID = "1p5L-2bCVYkOdNgFWi6XF49yKdwacDBhI"

PENDING_SEARCHES = {}

def graceful_reload():
    """Render'ı kızdırmadan, arka plandaki Gunicorn işçisini kibarca sıfırlar."""
    time.sleep(1)
    print("♻️ Uptime Robot tetikledi: RAM temizliği için işçi yenileniyor...")
    os.kill(os.getpid(), signal.SIGHUP)

# --- ROBOT UYANDIRMA VE HAFIZA SIFIRLAMA ---
@app.route('/', methods=['GET'])
def home():
    """Uptime Robot her 5 dakikada bir buraya uğradığında, 
    bot hem 200 OK verir hem de arka planda RAM'ini sıfırlar."""
    threading.Thread(target=graceful_reload).start()
    return "Bosphore Filter Bot Aktif ve Canlı! 🟢", 200

def search_all_pdfs_in_drive(file_name_keyword):
    """Google Drive klasöründe ismi eşleşen TÜM dosya türlerini listeler."""
    try:
        drive_service = build('drive', 'v3', developerKey=DRIVE_API_KEY)
        query = f"'{DRIVE_FOLDER_ID}' in parents and name contains '{file_name_keyword}' and trashed = false"
        results = drive_service.files().list(
            q=query, 
            spaces='drive', 
            fields='files(id, name, webViewLink)',
            pageSize=10
        ).execute()
        
        files = results.get('files', [])
        drive_service.close()
        return files
    except Exception as e:
        print(f"Drive Arama Hatası: {e}")
        return []

def send_whatsapp_message(remote_jid, text):
    """Evolution API üzerinden WhatsApp'a doğrudan mesaj gönderir."""
    send_url = f"{EVO_URL}/message/sendText/bosphore_ana_bot"
    headers = {"apikey": EVO_API_KEY, "Content-Type": "application/json"}
    
    payload = {
        "number": remote_jid,
        "text": text,
        "delay": 1200,
        "linkPreview": True
    }
    
    try:
        response = requests.post(send_url, json=payload, headers=headers)
        print(f"📨 Mesaj Gönderme Durumu: {response.status_code}")
    except Exception as e:
        print(f"Mesaj gönderme hatası: {e}")

def clean_search_keyword(text):
    """Kullanıcının mesajındaki gereksiz arama kelimelerini temizler."""
    keyword = text.replace("kılavuz", "").strip()
    stop_words = ["var mı", "varmı", "bul", "getir", "ara", "lazım", "arıyorum", "nerede", "nerde", "lütfen", "pdf", "pdfi"]
    for word in stop_words:
        if keyword.endswith(word):
            keyword = keyword[:keyword.rfind(word)].strip()
        keyword = keyword.replace(word, "").strip()
    return keyword.strip()

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    
    try:
        if data and 'data' in data and 'message' in data['data']:
            msg_data = data['data']['message']
            remote_jid = data['data']['key']['remoteJid']
            
            message_text = ""
            if 'conversation' in msg_data:
                message_text = msg_data['conversation']
            elif 'extendedTextMessage' in msg_data and 'text' in msg_data['extendedTextMessage']:
                message_text = msg_data['extendedTextMessage']['text']
                
            message_text = message_text.strip()
            message_text_lower = message_text.lower()
            
            # --- DURUM 1: ARAMA TETİKLENME ---
            if message_text_lower.startswith("kılavuz"):
                PENDING_SEARCHES.pop(remote_jid, None)
                
                search_keyword = clean_search_keyword(message_text_lower)
                if not search_keyword:
                    return jsonify({"status": "success"}), 200
                    
                print(f"🔍 Arama Kelimesi: {search_keyword}")
                found_files = search_all_pdfs_in_drive(search_keyword)
                
                if not found_files:
                    send_whatsapp_message(remote_jid, f"Aradığınız '{search_keyword}' dokümanı maalesef klasörde bulunamadı. ❌")
                    gc.collect()
                    return jsonify({"status": "success"}), 200
                
                if len(found_files) == 1:
                    file_name = found_files[0]['name']
                    file_link = found_files[0]['webViewLink']
                    reply = f"İstediğiniz *{file_name}* dokümanı bulundu! ✅\n\n🔗 Doküman Linki:\n{file_link}"
                    send_whatsapp_message(remote_jid, reply)
                else:
                    PENDING_SEARCHES[remote_jid] = {"files": found_files}
                    reply_text = f"🔍 *Birden fazla sonuç buldum!*\nLütfen istediğiniz dokümanın numarasını yazın (Örn: *1* veya *2*):\n\n"
                    for index, file in enumerate(found_files, start=1):
                        reply_text += f"*{index}* - {file['name']}\n"
                    send_whatsapp_message(remote_jid, reply_text)
            
            # --- DURUM 2: SAYI SEÇİMİ ---
            elif remote_jid in PENDING_SEARCHES and message_text.isdigit():
                selected_index = int(message_text) - 1
                saved_data = PENDING_SEARCHES[remote_jid]
                user_files = saved_data["files"]
                
                if 0 <= selected_index < len(user_files):
                    chosen_file = user_files[selected_index]
                    file_name = chosen_file['name']
                    file_link = chosen_file['webViewLink']
                    
                    reply = f"Seçtiğiniz *{file_name}* dokümanı hazır. 📄\n\n🔗 Doküman Linki:\n{file_link}"
                    send_whatsapp_message(remote_jid, reply)
                    PENDING_SEARCHES.pop(remote_jid, None)
                else:
                    send_whatsapp_message(remote_jid, f"⚠️ Geçersiz numara. Lütfen listedeki rakamlardan birini yazın.")
                    
    except Exception as e:
        print(f"🤖 Webhook işlem hatası: {e}")
        
    finally:
        gc.collect()
        
    return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
