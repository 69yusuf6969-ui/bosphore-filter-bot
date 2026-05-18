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

# Kullanıcıların bekleyen arama sonuçlarını hafızada tutmak için geçici bir sözlük
# Format: { "kullanıcı_whatsapp_id": [ {"name": "...", "webViewLink": "..."}, ... ] }
PENDING_SEARCHES = {}

def search_all_pdfs_in_drive(file_name_keyword):
    """Google Drive klasöründe isminde keyword geçen TÜM PDF'leri listeler."""
    try:
        drive_service = build('drive', 'v3', developerKey=DRIVE_API_KEY)
        
        # Klasör içinde, isminde keyword geçen, silinmemiş tüm PDF'leri ara
        query = f"'{DRIVE_FOLDER_ID}' in parents and name contains '{file_name_keyword}' and mimeType = 'application/pdf' and trashed = false"
        
        results = drive_service.files().list(
            q=query, 
            spaces='drive', 
            fields='files(id, name, webViewLink)',
            pageSize=10  # En fazla 10 sonuç listelesin
        ).execute()
        
        return results.get('files', [])
    except Exception as e:
        print(f"Drive Arama Hatası: {e}")
        return []

def send_whatsapp_message(remote_jid, instance_name, text):
    """Evolution API üzerinden WhatsApp'a mesaj gönderir."""
    send_url = f"{EVO_URL}/message/sendText/{instance_name}"
    headers = {"apikey": EVO_API_KEY, "Content-Type": "application/json"}
    payload = {
        "number": remote_jid,
        "text": text,
        "delay": 1200,
        "linkPreview": True
    }
    response = requests.post(send_url, json=payload, headers=headers)
    print(f"📨 Mesaj Gönderme Durumu: {response.status_code}")

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    
    try:
        if data and 'data' in data and 'message' in data['data']:
            msg_data = data['data']['message']
            remote_jid = data['data']['key']['remoteJid']
            instance_name = data['instance']
            
            # Mesaj metnini temizle
            message_text = ""
            if 'conversation' in msg_data:
                message_text = msg_data['conversation']
            elif 'extendedTextMessage' in msg_data and 'text' in msg_data['extendedTextMessage']:
                message_text = msg_data['extendedTextMessage']['text']
                
            message_text = message_text.strip()
            message_text_lower = message_text.lower()
            
            # --- DURUM 1: YENİ ARAMA BAŞLATMA (kılavuz hcv vb.) ---
            if message_text_lower.startswith("kılavuz "):
                search_keyword = message_text_lower.replace("kılavuz ", "").strip()
                print(f"🔍 Çoklu Arama Başlatıldı: {search_keyword}")
                
                # Drive'dan eşleşen tüm dosyaları getir
                found_files = search_all_pdfs_in_drive(search_keyword)
                
                if not found_files:
                    send_whatsapp_message(remote_jid, instance_name, f"❌ Maalesef klasörde içinde '{search_keyword}' geçen hiçbir kılavuz PDF'i bulunamadı.")
                    return jsonify({"status": "success"}), 200
                
                # Sadece 1 tane dosya bulunduysa direkt gönder, seçtirip uğraştırma
                if len(found_files) == 1:
                    file_name = found_files[0]['name']
                    file_link = found_files[0]['webViewLink']
                    reply = f"📄 *{file_name}* bulundu!\n\n🔗 Doküman Linki:\n{file_link}"
                    send_whatsapp_message(remote_jid, instance_name, reply)
                    
                    # Eğer bu kullanıcının eski bir seçimi kaldıysa temizle
                    PENDING_SEARCHES.pop(remote_jid, None)
                    
                # Birden fazla dosya bulunduysa listele ve hafızaya al
                else:
                    PENDING_SEARCHES[remote_jid] = found_files
                    
                    reply_text = f"🔍 *Birden fazla sonuç bulundu!*\n"
                    reply_text += f"Lütfen istediğiniz kılavuzun numarasını yazın (Örn: *1* veya *2*):\n\n"
                    
                    for index, file in enumerate(found_files, start=1):
                        reply_text += f"*{index}* - {file['name']}\n"
                        
                    send_whatsapp_message(remote_jid, instance_name, reply_text)
            
            # --- DURUM 2: NUMARA SEÇİMİ YAPMA (1, 2, 3 vb.) ---
            elif remote_jid in PENDING_SEARCHES and message_text.isdigit():
                selected_index = int(message_text) - 1
                user_files = PENDING_SEARCHES[remote_jid]
                
                # Yazılan numara listede var mı kontrol et
                if 0 <= selected_index < len(user_files):
                    chosen_file = user_files[selected_index]
                    file_name = chosen_file['name']
                    file_link = chosen_file['webViewLink']
                    
                    reply = f"📄 *{file_name}* seçildi.\n\n🔗 Doküman Linki:\n{file_link}"
                    send_whatsapp_message(remote_jid, instance_name, reply)
                    
                    # İşlem bittiği için kullanıcının geçici hafızasını temizle
                    del PENDING_SEARCHES[remote_jid]
                else:
                    send_whatsapp_message(remote_jid, instance_name, f"⚠️ Geçersiz numara. Lütfen listedeki rakamlardan (1 ile {len(user_files)} arası) birini yazın.")
                    
    except Exception as e:
        print(f"🤖 Webhook işlem hatası: {e}")
        
    return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)