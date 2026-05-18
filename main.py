import os
import requests
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

def search_all_pdfs_in_drive(file_name_keyword):
    """Google Drive klasöründe isminde keyword geçen TÜM PDF'leri listeler."""
    try:
        drive_service = build('drive', 'v3', developerKey=DRIVE_API_KEY)
        query = f"'{DRIVE_FOLDER_ID}' in parents and name contains '{file_name_keyword}' and mimeType = 'application/pdf' and trashed = false"
        results = drive_service.files().list(
            q=query, 
            spaces='drive', 
            fields='files(id, name, webViewLink)',
            pageSize=10
        ).execute()
        return results.get('files', [])
    except Exception as e:
        print(f"Drive Arama Hatası: {e}")
        return []

def send_whatsapp_message(remote_jid, text, push_name=None):
    """Evolution API üzerinden WhatsApp'a mesaj gönderir."""
    # BURASI DÜZELTİLDİ: Artık doğrudan senin paneldeki "bosphore_ana_bot" ismini kullanıyor.
    send_url = f"{EVO_URL}/message/sendText/bosphore_ana_bot"
    headers = {"apikey": EVO_API_KEY, "Content-Type": "application/json"}
    
    final_text = text
    if push_name and "@g.us" in remote_jid:
        final_text = f"✍️ *{push_name}*, {text}"
        
    payload = {
        "number": remote_jid,
        "text": final_text,
        "delay": 1200,
        "linkPreview": True
    }
    
    response = requests.post(send_url, json=payload, headers=headers)
    print(f"📨 Mesaj Gönderme Durumu: {response.status_code}")

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
            
            # WhatsApp Profil İsmini Yakala
            push_name = data['data'].get('pushName', 'Kullanıcı')
            
            message_text = ""
            if 'conversation' in msg_data:
                message_text = msg_data['conversation']
            elif 'extendedTextMessage' in msg_data and 'text' in msg_data['extendedTextMessage']:
                message_text = msg_data['extendedTextMessage']['text']
                
            message_text = message_text.strip()
            message_text_lower = message_text.lower()
            
            # --- DURUM 1: ARAMA TETİKLENME ---
            if message_text_lower.startswith("kılavuz"):
                search_keyword = clean_search_keyword(message_text_lower)
                
                if not search_keyword:
                    return jsonify({"status": "success"}), 200
                    
                print(f"🔍 İsimli Arama Kelimesi: {search_keyword} ({push_name})")
                
                found_files = search_all_pdfs_in_drive(search_keyword)
                
                if not found_files:
                    send_whatsapp_message(remote_jid, f"aradığınız '{search_keyword}' kılavuzu maalesef klasörde bulunamadı. ❌", push_name)
                    return jsonify({"status": "success"}), 200
                
                if len(found_files) == 1:
                    file_name = found_files[0]['name']
                    file_link = found_files[0]['webViewLink']
                    reply = f"istediğiniz *{file_name}* kılavuzu bulundu! ✅\n\n🔗 Doküman Linki:\n{file_link}"
                    send_whatsapp_message(remote_jid, reply, push_name)
                    PENDING_SEARCHES.pop(remote_jid, None)
                else:
                    PENDING_SEARCHES[remote_jid] = {
                        "files": found_files,
                        "name": push_name
                    }
                    reply_text = f"🔍 *Birden fazla sonuç buldum!*\nLütfen istediğiniz kılavuzun numarasını yazın (Örn: *1* veya *2*):\n\n"
                    for index, file in enumerate(found_files, start=1):
                        reply_text += f"*{index}* - {file['name']}\n"
                    send_whatsapp_message(remote_jid, reply_text, push_name)
            
            # --- DURUM 2: SAYI SEÇİMİ ---
            elif remote_jid in PENDING_SEARCHES and message_text.isdigit():
                selected_index = int(message_text) - 1
                saved_data = PENDING_SEARCHES[remote_jid]
                user_files = saved_data["files"]
                original_name = saved_data["name"]
                
                if 0 <= selected_index < len(user_files):
                    chosen_file = user_files[selected_index]
                    file_name = chosen_file['name']
                    file_link = chosen_file['webViewLink']
                    
                    reply = f"seçtiğiniz *{file_name}* kılavuzu hazır. 📄\n\n🔗 Doküman Linki:\n{file_link}"
                    send_whatsapp_message(remote_jid, reply, original_name)
                    del PENDING_SEARCHES[remote_jid]
                else:
                    send_whatsapp_message(remote_jid, f"⚠️ Geçersiz numara. Lütfen listedeki rakamlardan birini yazın.", original_name)
                    
    except Exception as e:
        print(f"🤖 Webhook işlem hatası: {e}")
        
    return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)