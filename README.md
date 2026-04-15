# Odeme Destek Ajansi

Reddedilen odemeleri arastirmak icin tasarlanmis hibrit ajantik bir sistem.
Claude (LLM) niyet anlama, arac secimi ve yanit uretiminden sorumluyken,
ince bir Python orkestrasyon katmani calistirma guvenligi, durum takibi ve
hata yonetimini ustlenir.

---

## Proje Ozeti

Kullanici serbest dilde bir soru sorar (ornegin "Duunku odemem neden reddedildi?").
Sistem su adimlari calisma zamaninda, LLM'in karar vermesiyle yurutur:

1. E-posta adresini kullanicidan alir (eksikse sorar)
2. E-posta ile kullanici bilgilerini arar
3. Kullanicinin son islemlerini ceker
4. Basarisiz islemi belirler (birden fazlaysa aciklama ister)
5. Red nedenini sorgular
6. Dogal dilde yanit olusturur

Bu adim sirasi sabit kodlanmis bir pipeline degildir. Her adimda LLM, eldeki
duruma bakarak sonraki aksiyona karar verir. Orkestrasyon katmani yalnizca
guvenlik kontrolu yapar ve durumu gunceller.

---

## Mimari Yaklasim

```
+--------------------------------------------+
|               Kullanici (CLI)              |
+---------------------+----------------------+
                      |
               +------v------+
               | Orchestrator |  <-- iteratif ajan dongusu
               | (agent/)     |
               +--+-------+--+
                  |       |
     +------------v-+  +--v--------------+
     |  LLM Client  |  | Guarded Dispatch|
     |  (Claude API) |  | (selector.py)  |
     +--------------+  +--+--------------+
                          |
               +----------v----------+
               |   Arac Fonksiyonlari |
               |   (tools/*.py)       |
               |   her cagri JSON'dan |
               |   taze okur          |
               +----------------------+
```

### Neden Hibrit Mimari?

Bu projede iki asiri uca dusulmemesi gereken bir denge vardir:

**Yalnizca prompt'a dayanan sistemler kirilgandir.** LLM bir parametreyi
uydurursa veya bir adimdaki veriyi halusinasyonla doldurursa, tum akis
bozulur. Prompt kurallari tek basina bunu onleyemez.

**Yalnizca koda dayanan pipeline'lar katıdır.** `if email then get_user then
get_transactions...` seklinde sabit kodlanmis bir zincir, belirsiz veya eksik
kullanici girdilerini yonetemez. Kullanici "duunku islem neden olmadi?" dediginde
bu pipeline hangi e-postayi kullanacagini bilemez.

Hibrit yaklasim isi ikiye boler:

| Sorumluluk | Sahip |
|---|---|
| Kullanici niyetini anlama | LLM |
| Dogal dilden entity cikarma | LLM |
| Hangi aracin cagirilacagina karar verme | LLM |
| Aciklama sorusu sorma karari | LLM |
| Son yanitı olusturma | LLM |
| Arac on-kosul dogrulamasi | Kod (selector.py) |
| Istisna yakalama | Kod (selector.py) |
| Ajan durumunu guncelleme | Kod (responder.py) |
| Iterasyon limitini zorlama | Kod (orchestrator.py) |
| Her adimi loglama | Kod (tum moduller) |

---

## Katmanlarin Sorumluluklari

### Karar Katmani (LLM)

LLM, sistemin beynidir. Her turda su kararlardan birini verir:

- **Arac cagirma**: hangi araci, hangi parametrelerle cagiracagini secer
- **Aciklama sorusu**: eksik bilgi varsa kullaniciya sorar
- **Son yanit**: yeterli bilgi toplandiysa dogal dilde cevap verir

LLM bu karari conversation history + tool result'lara bakarak verir.
Orkestrasyon katmani bu karara mudahale etmez.

### Calistirma Katmani (Kod)

Orkestrasyon katmani kasitli olarak incedir. Gorevleri:

1. **On-kosul kontrolu** (`selector.py`): Arac parametrelerinin bos olmadigini
   dogrular. Ornegin `get_recent_transactions` icin `user_id` parametresinin
   mevcut olmasini zorunlu kilar.

2. **Istisna yakalama** (`selector.py`): Arac cagrilari sirasinda olusan
   `UserNotFoundError`, `FraudReasonNotFoundError` veya beklenmeyen hatalari
   yakalar ve yapisal bir hata mesaji olarak LLM'e geri dondurur.

3. **Durum guncelleme** (`responder.py`): Basarili arac sonuclarindan
   `user_id`, `email`, `candidate_transactions` gibi alanlari state'e yazar.

4. **Iterasyon limiti** (`orchestrator.py`): LLM sonsuz donguye girerse
   maksimum 10 iterasyondan sonra durur.

### Neden Guard Katmani Ince?

Guard katmani kasitli olarak yalnizca parametrelerin bosluğunu kontrol eder.
Ornegin LLM'in gonderdigi `user_id`'nin state'teki `user_id` ile ayni olup
olmadigini dogrulamaz. Bu bir eksiklik degil, bilinçli bir tasarim tercihi:

- Eger guard katmani semantik dogruluk da zorlarsa (ornegin "bu transaction_id
  gercekten candidate_transactions icinde mi?"), orkestrasyon katmani is akisini
  kontrol etmeye baslar ve LLM'in karar verme rolu zayiflar.
- Boyle bir sistem artik ajan degil, LLM-dekorasyonlu bir deterministic pipeline
  olur.
- Guard yalnizca "bu cagri teknik olarak gecerli mi?" sorusunu cevaplar.
  "Bu cagri mantikli mi?" sorusu LLM'in sorumlulugundadir.

Bu tradeoff, ajanin gercekten ajantik kalmasini saglar. Yanlis bir parametre
geçerse araç hata dondurur, LLM bu hatayi gorur ve kendi basina duzeltir.

---

## Araclar (Tool'lar)

### `get_user_details(email: str)`
- **Donus**: `{ user_id, account_status }`
- **Hata**: E-posta bulunamazsa `UserNotFoundError`
- **On-kosul**: `email` bos olamaz (guard tarafindan zorunlu kilindi)

### `get_recent_transactions(user_id: str, limit: int)`
- **Donus**: `{ transaction_id, amount, status, created_at }` listesi, `created_at`'e gore azalan sirada
- **On-kosul**: `user_id` bos olamaz (guard tarafindan zorunlu kilindi)

### `check_fraud_reason(transaction_id: str)`
- **Donus**: `{ transaction_id, reason }`
- **Hata**: Sebep kaydi yoksa `FraudReasonNotFoundError`
- **On-kosul**: `transaction_id` bos olamaz (guard tarafindan zorunlu kilindi)

**Arac Sonuc Formati**: Her arac sonucu orkestrasyon katmani tarafindan
`{"success": true, "data": ...}` veya `{"success": false, "error": "..."}` olarak
sarmalanir. LLM bu formati system prompt araciligiyla bilir ve buna gore islem yapar.

---

## Durum Yonetimi

`AgentState` (`agent/state.py`) ajansa surecinde biriken bilgiyi tutar:

| Alan | Kaynak | Aciklama |
|---|---|---|
| `conversation_history` | Orchestrator | Tum mesaj gecmisi (multi-turn icin) |
| `current_user_message` | Orchestrator | Mevcut tur kullanici mesaji |
| `email` | responder (tool_args'tan) | Aranan e-posta adresi |
| `user_id` | responder (tool sonucundan) | Bulunan kullanici ID'si |
| `account_status` | responder (tool sonucundan) | Hesap durumu |
| `candidate_transactions` | responder (tool sonucundan) | Son islemler listesi |
| `selected_transaction_id` | responder (tool sonucundan) | Fraud sebebi sorgulanan islem |
| `last_tool_result` | responder | Son arac sonucu |
| `final_answer` | Orchestrator | LLM'in verdigi son cevap |
| `error` | responder / Orchestrator | Son hata mesaji |

**Tasarim prensibi**: State'te yalnizca calisma zamaninda gercekten okunan ve
yazilan alanlar bulunur. Kullanilmayan alanlar bilinçli olarak cikarilmistir.

Multi-turn destek: `conversation_history` turler arasinda korunur. Kullanici
ilk turda e-posta vermezse, ikinci turda verdiginde LLM onceki baglami gorur
ve kaldigi yerden devam eder.

---

## Hata Yonetimi

Sistem asla kullanici karsisinda cokmez. Hata akislari:

| Senaryo | Davranis |
|---|---|
| E-posta verilmemis | LLM e-postayi sorar |
| Hatali/bilinmeyen e-posta | `UserNotFoundError` yakalanir, LLM aciklar |
| Islem bulunamadi | Bos liste donulur, LLM bilgilendirir |
| Basarisiz islem yok | LLM tum islemlerin basarili oldugunu soyler |
| Birden fazla basarisiz islem | LLM secenekleri listeler, aciklama ister |
| Fraud sebebi eksik | `FraudReasonNotFoundError` yakalanir, LLM aciklar |
| Basarili islem reddedilmis gibi sorulursa | LLM duzeltir |
| Beklenmeyen arac hatasi | `guarded_dispatch` yakalar, yapisal hata doner |
| LLM API hatasi | Orchestrator yakalar, kullanici dostu mesaj verir |
| Bozuk JSON dosyasi | Generic exception yakalanir, yapisal hata doner |
| Sonsuz dongu | Maks. 10 iterasyondan sonra durur |

---

## Test Yaklasimi

### Neden LLM Yanıtlari Mock'laniyor?

Testler `MockLLMClient` kullanir: LLM'in her adimda ne yanit verecegi onceden
belirlenir. Bu, testlerin **orkestrasyon katmanini** deterministik sekilde
dogrulamasini saglar:

- Arac cagrilari dogru argümanlarla yürütüluyor mu?
- Arac sonuclari state'e dogru yaziliyor mu?
- Hatalar yakalanip yapisal sekilde donduruluyor mu?
- Conversation history dogru birikiyor mu?
- Multi-turn baglam korunuyor mu?

**Onemli**: Mock LLM kullanmak, uretim kodunun deterministik bir zincir oldugu
anlamina gelmez. Uretim kodunda `orchestrator.py` her turda Claude API'a tam
conversation history gonderir ve LLM'in verdigi karar ne ise onu yurutur.
Bagimlilik zinciri (email -> user_id -> transactions -> fraud_reason) modelin
akil yurutmesinden, arac geri bildirimlerinden ve state'ten ortaya cikar,
sabit kodlanmis bir pipeline'dan degil.

Mock testler orkestrasyon boru hattinin dogru calistigini kanitlar.
Gercek LLM davranisi ise `python app.py` ile canli test edilebilir.

### Test Dosyalari

| Dosya | Senaryo |
|---|---|
| `test_happy_path.py` | Tam zincir: email -> user -> transactions -> fraud reason -> yanit |
| `test_missing_email.py` | E-posta eksik -> ajan sorar -> ikinci turda devam eder |
| `test_unknown_user.py` | Bilinmeyen e-posta -> yapisal hata -> dogal aciklama |
| `test_multiple_failed.py` | Birden fazla basarisiz islem -> aciklama istenir -> cozumlenir |
| `test_mutated_data.py` | JSON dosyalari degistirilir -> sonraki arac cagrisi yeni veriyi kullanir |
| `test_edge_cases.py` | Bos parametre, bozuk JSON, sonsuz dongu, API hatasi, ve diger uc durumlar |

---

## Mock Veri Tasarimi

Mock veritabani `data/` dizinindeki JSON dosyalarindan olusur:

- `users.json` — 3 kullanici (aktif, aktif, askiya alinmis)
- `transactions.json` — 6 islem (basarili ve basarisiz karisik, USR002'nin 2 basarisiz islemi var)
- `fraud_reasons.json` — 4 red sebebi kaydi

### Neden Her Cagri Taze Okuma Yapar?

Her arac fonksiyonu (`get_user_details`, `get_recent_transactions`,
`check_fraud_reason`) çagrildiginda JSON dosyasini diskten yeniden okur.
Bellek ici onbellekleme (cache) yoktur.

Bu tasarim kritiktir cunku:

- Degerlendirici (`evaluator`) testler sirasinda `data/*.json` dosyalarini
  manuel olarak degistirebilir
- Bir fraud sebebi metni degistirildiginde, bir sonraki `check_fraud_reason`
  cagrisi yeni metni donmelidir
- Eger cache olsaydi, degistirilen veri yansimaz ve test basarisiz olurdu

`test_mutated_data.py` bu davranisi kanitlar: dosya degistirilir, arac
cagirilir, yeni deger dogrulanir, dosya geri yuklenir.

---

## Proje Yapisi

```
├── app.py                    # CLI giris noktasi
├── agent/
│   ├── orchestrator.py       # Ajan dongusu
│   ├── state.py              # AgentState dataclass
│   ├── prompts.py            # System prompt
│   ├── llm_client.py         # Anthropic API sarimlayici
│   ├── selector.py           # Guarded dispatch + on-kosullar
│   └── responder.py          # Sonuc formatlama + state guncelleme
├── tools/
│   ├── user_tools.py         # get_user_details
│   ├── transaction_tools.py  # get_recent_transactions
│   ├── fraud_tools.py        # check_fraud_reason
│   ├── schemas.py            # Claude arac tanimlari
│   └── errors.py             # Ozel istisna siniflari
├── data/
│   ├── users.json
│   ├── transactions.json
│   └── fraud_reasons.json
├── tests/
│   ├── conftest.py           # Mock LLM client
│   ├── test_happy_path.py
│   ├── test_missing_email.py
│   ├── test_unknown_user.py
│   ├── test_multiple_failed.py
│   ├── test_mutated_data.py
│   └── test_edge_cases.py
├── requirements.txt
└── README.md
```

---

## Nasil Calistirilir

```bash
# 1. Bagimliliklari yukle
pip install -r requirements.txt

# 2. Anthropic API anahtarini ayarla
export ANTHROPIC_API_KEY="sk-ant-..."

# 3. (Istege bagli) Modeli degistir
export ANTHROPIC_MODEL="claude-sonnet-4-20250514"

# 4. Ajanı baslat
python app.py
```

Ornek oturum:

```
You: ali@sirket.com adresimle duunku odemem neden reddedildi?
Agent: 14 Nisan'daki 1.500 TL'lik odemeniz, fraud tespit sistemimiz
       tarafindan normal cografi bolgeniz disinda olagan disi bir
       harcama kalıbi tespit edildigi icin reddedildi.

You: reset
(conversation reset)

You: Odemem neden reddedildi?
Agent: Yardimci olmak isterim. Lutfen e-posta adresinizi paylasir misiniz?

You: ali@sirket.com
Agent: ...
```

`quit` yazarak cikin, `reset` yazarak konusmayi sifirlayin.

---

## Testler Nasil Kosulur

Testler mock LLM kullanir — API anahtari gerekmez.

```bash
pytest tests/ -v
```

---

## Degerlendirme Acisindan Guclu Yonler

1. **Gercek hibrit tasarim**: LLM karar verir, kod guvenlik saglar. Ikisi
   birbirinin alanina girmez.

2. **Is akisi sabit kodlanmamis**: `email -> user_id -> transactions -> fraud_reason`
   zinciri LLM'in akıl yurutmesinden ortaya cikar, bir `if/else` pipeline'indan
   degil. LLM farkli bir sira izlemek isterse orkestrasyon buna engel olmaz.

3. **Guard katmani ince ve acilanabilir**: On-kosullar yalnizca parametre
   bosluğunu kontrol eder. Neden semantik dogruluk zorlanmadigini (ornegin
   `user_id` cross-validation) aciklayabilir ve savunabilirsiniz: guard
   katmani kalinlastikca ajan olmaktan cikar.

4. **Mock veri degisikligine dayanikli**: Degerlendirici `fraud_reasons.json`'i
   degistirirse sistem yeni degeri kullanir. `test_mutated_data.py` bunu kanitlar.

5. **State durust ve minimal**: Yalnizca calisma zamaninda gercekten okunan ve
   yazilan alanlar vardir. Kullanilmayan alanlar cikarilmistir.

6. **Kapsamli hata yonetimi**: Bilinen hatalar (`UserNotFoundError`,
   `FraudReasonNotFoundError`), beklenmeyen hatalar, bozuk JSON, API hatasi
   ve sonsuz dongu dahil 11 farkli hata senaryosu ele alinir.

7. **Multi-turn destek**: Kullanici ilk turda eksik bilgi verirse, ikinci turda
   tamamlayabilir. Conversation history turler arasinda korunur.

8. **Test stratejisi acilanabilir**: Mock testlerin neden kullanildigini,
   bunun deterministik zincir anlamina gelmedigini, ve uretim kodundaki
   farki aciklayabilirsiniz.
