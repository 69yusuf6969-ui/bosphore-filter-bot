from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# Render çevre değişkenleri
EVO_URL = os.getenv("EVO_URL", "https://evolution-api-awf2.onrender.com")
API_KEY = os.getenv("API_KEY", "Bosphore2026!")
INSTANCE_NAME = os.getenv("INSTANCE_NAME", "bosphore_ana_bot")

# 🎯 SADECE TEST ADLARI VE GOOGLE DRIVE LİNKLERİ
# Link kısımlarını kendi Drive paylaşım linklerinizle değiştirebilirsiniz.
test_kilavuzlari = {
    "hbv": "📌 HBV Kılavuzu PDF dosyasına aşağıdaki linkten ulaşabilirsiniz:\n🔗 https://drive.google.com/file/d/SİZİN_HBV_DRIVE_LİNKİNİZ/view?usp=sharing",
    "hcv": "📌 HCV Kılavuzu PDF dosyasına aşağıdaki linkten ulaşabilirsiniz:\n🔗 https://drive.google.com/file/d/SİZİN_HCV_DRIVE_LİNKİNİZ/view?usp=sharing",
    "hpv": "📌 HPV Kılavuzu PDF dosyasına aşağıdaki linkten ulaşabilirsiniz:\n🔗 https://drive.google.com/file/d/SİZİN_HPV_DRIVE_LİNKİNİZ/view?usp=sharing"
}

@app.route('/webhook', methods=['POST'])
def whatsapp_webhook():
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "No data received"}), 400
    
    try:
        message_data = data.get('data', {})
        message_type = message_data.get('messageType')
        from_me = message_data.get('key', {}).get('fromMe', False)
        remote_jid = message_data.get('key', {}).get('remoteJid', '')

        # Bizim gönderdiğimiz mesajları veya boş verileri pas geç
        if from_me or not remote_jid:
            return jsonify({"status": "ignored"}), 200

        # Metni ayıkla
        message_text = ""
        if message_type == "conversation":
            message_text = message_data.get('message', {}).get('conversation', '')
        elif message_type == "extendedTextMessage":
            message_text = message_data.get('message', {}).get('extendedTextMessage', {}).get('text', '')

        # Küçük harfe çevir ve boşlukları temizle
        cleaned_text = message_text.strip().lower()

        # 🎯 SADECE "kılavuz " ile başlıyorsa kontrol et
        if cleaned_text.startswith("kılavuz"):
            # "kılavuz hbv" -> "hbv" kısmını yalnız bırakıyoruz
            test_adi = cleaned_text.replace("kılavuz", "").strip()
            
            # Yazılan test adı listemizde var mı?
            if test_adi in test_kilavuzlari:
                cevap = test_kilavuzlari[test_adi]
                
                # WhatsApp'a Drive linkini içeren mesajı gönder
                send_url = f"{EVO_URL}/message/sendText/{INSTANCE_NAME}"
                headers = {"apikey": API_KEY, "Content-Type": "application/json"}
                payload = {
                    "number": remote_jid.split("@")[0],
                    "text": cevap
                }
                requests.post(send_url, json=payload, headers=headers)
                print(f"✅ Kılavuz Gönderildi: {test_adi}")
            else:
                # Test adı eşleşmediyse bot sessiz kalır, hiçbir şey göndermez
                print(f"❓ Bilinmeyen test adı, cevap verilmedi: {test_adi}")
        else:
            # "kılavuz" ile başlamayan hiçbir mesaja dönüp bakmaz
            print(f"😴 Normal mesaj pas geçildi: {cleaned_text}")

    except Exception as e:
        print("Hata oluştu:", str(e))

    return jsonify({"status": "SUCCESS"}), 200

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port)