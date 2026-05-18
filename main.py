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

def search_pdf_in_drive(file_name_keyword):
    """Google Drive klasöründe isme göre PDF arar ve linkini döner."""
    try:
        drive_service = build('drive', 'v3', developerKey=DRIVE_API_KEY)
        
        # Klasör içinde, isminde keyword geçen, silinmemiş PDF'leri ara
        query = f"'{DRIVE_FOLDER_ID}' in parents and name contains '{file_name_keyword}' and mimeType = 'application/pdf' and trashed = false"
        
        results = drive_service.files().list(
            q=query, 
            spaces='drive', 
            fields='files(id, name, webViewLink)'
        ).execute()
        
        items = results.get('files', [])
        
        if not items:
            return None
        
        # İlk bulunan dosyanın adını ve önizleme linkini döndür
        return items[0]
    except Exception as e:
        print(f"Drive Arama Hatası: {e}")
        return None

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    
    try:
        # Gelen verinin bir mesaj olup olmadığını kontrol et
        if data and 'data' in data and 'message' in data['data']:
            msg_data = data['data']['message']
            
            # Mesajın metin içeriğini al
            message_text = ""
            if 'conversation' in msg_data:
                message_text = msg_data['conversation']
            elif 'extendedTextMessage' in msg_data and 'text' in msg_data['extendedTextMessage']:
                message_text = msg_data['extendedTextMessage']['text']
                
            message_text = message_text.strip().lower()
            
            # Eğer mesaj "kılavuz " ile başlıyorsa
            if message_text.startswith("kılavuz "):
                search_keyword = message_text.replace("kılavuz ", "").strip()
                
                remote_jid = data['data']['key']['remoteJid']
                instance_name = data['instance']
                
                print(f"🔍 Klasörde Aranıyor: {search_keyword}")
                
                # Google Drive klasöründe ara
                found_file = search_pdf_in_drive(search_keyword)
                
                if found_file:
                    file_name = found_file['name']
                    file_link = found_file['webViewLink']
                    reply_text = f"📄 *{file_name}* bulundu!\n\n🔗 Doküman Linki:\n{file_link}"
                else:
                    reply_text = f"❌ Maalesef klasörde içinde '{search_keyword}' geçen bir kılavuz PDF'i bulunamadı."
                
                # Evolution API üzerinden WhatsApp'a cevap gönder
                send_url = f"{EVO_URL}/message/sendText/{instance_name}"
                headers = {"apikey": EVO_API_KEY, "Content-Type": "application/json"}
                payload = {
                    "number": remote_jid,
                    "text": reply_text,
                    "delay": 1200,
                    "linkPreview": True
                }
                
                response = requests.post(send_url, json=payload, headers=headers)
                print(f"📨 Mesaj Gönderme Durumu: {response.status_code}")
                
    except Exception as e:
        print(f"🤖 Webhook işlem hatası: {e}")
        
    return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)