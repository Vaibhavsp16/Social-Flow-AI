"""
Localised message catalogue.

Every user-facing string the flow emits lives here, keyed by a stable id, so wording can be
changed (or another language added) without touching the conversation logic. Templates use
str.format placeholders.
"""

SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "हिन्दी",
    "gu": "ગુજરાતી",
    "mr": "मराठी",
}

DEFAULT_LANGUAGE = "en"

MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        # Greetings
        "greeting_morning": "Good morning! I'm {bot}, your property assistant.",
        "greeting_afternoon": "Good afternoon! I'm {bot}, your property assistant.",
        "greeting_evening": "Good evening! I'm {bot}, your property assistant.",
        "greeting_late_night": "Hello, you're up late! I'm {bot}, your property assistant.",
        "greeting_holiday": "Happy {holiday}! I'm {bot}, your property assistant.",
        "greeting_weather": "Lovely weather in {city} today — {weather}.",
        "greeting_weather_bad": "It's {weather} in {city} today, so a good day to browse indoors.",
        "ask_intent": "Are you looking to buy a home, find a rental, or just explore what's available?",
        "engagement_tea": "By the way — tea or coffee while you browse?",
        "engagement_weekend": "And how do you usually spend your weekends?",
        # Discovery
        "ask_location": "Which area are you considering? For example Ambli, Bopal, Satellite or SG Highway.",
        "ask_type": "What kind of property did you have in mind — an apartment, a villa, or a plot?",
        "ask_bhk": "How many bedrooms do you need — 2, 3 or 4 BHK?",
        "ask_budget": "What budget are you working with? A rough range is enough for me to filter.",
        "ask_budget_rent": "And what monthly rent are you comfortable with?",
        "ask_amenities": "Any must-haves in the property — pool, gym, parking, a garden?",
        "ask_timeline": "Are you looking to move in soon, or planning further ahead?",
        "ask_purpose": "Just so I point you in the right direction, is this for your family to live in, or an investment?",
        "ack": "Understood — {details}. ",
        # Shortlist
        "shortlist_one": "Here is one option {verb} that fits what you described:",
        "shortlist_many": "Here are {count} options {verb} that fit what you described:",
        "verb_sale": "for sale",
        "verb_rent": "on rent",
        "shortlist_followup": "Tell me which one you would like to know more about, or I can narrow these down further.",
        "no_match_area": "I couldn't find {criteria} in {area}, but these are the closest available options:",
        "no_match": "I could not find a match for those requirements in the current inventory. I can widen the area or budget — or have an advisor check upcoming options.",
        "advisor_offer": "Would you like an advisor to check availability and share the brochure? I can arrange a call.",
        "widen_offer": "Would you like me to widen the search, or have an advisor check upcoming options that aren't listed yet?",
        "browse_intro": "Here's a quick look at what's available right now.",
        "browse_hint": "If you tell me the area or budget you have in mind, I can narrow this down.",
        "detail_mock": "(This is development data, not a live listing.)",
        # Lead capture
        "lead_start": "Happy to arrange that. What name should the advisor ask for?",
        "lead_ask_phone": "Thanks, {name}. What's the best phone number to reach you on?",
        "lead_ask_email": "Got it. And an email address for the brochure? You can say 'skip' if you'd rather not share one.",
        "lead_ask_contact": "Last one — how would you prefer to be contacted: phone, WhatsApp or email?",
        "lead_phone_invalid": "That doesn't look like a complete number — could you share a 10-digit mobile number?",
        "lead_email_invalid": "That email doesn't look quite right — could you check it, or say 'skip'?",
        "lead_done": "All set, {name}. I've passed your details to the Prycoons advisor team — they'll contact you by {contact} on {phone}.",
        "lead_done_email": " The brochure will go to {email}.",
        "lead_done_end": "Anything else you'd like to know while you wait?",
        # Handoff
        "handoff": "Of course. I'm flagging this conversation for a human advisor now, and someone from the Prycoons team will reach out shortly.\n\nIf you'd like a callback, share the best number and a convenient time and I'll add it to the note.",
        "lead_declined": "No problem at all — I'll leave you to browse. I'm here if you'd like details on any of these, or want me to look at other areas.",
    },
    "hi": {
        "greeting_morning": "सुप्रभात! मैं {bot} हूँ, प्राइकून्स का प्रॉपर्टी सहायक।",
        "greeting_afternoon": "नमस्कार! मैं {bot} हूँ, प्राइकून्स का प्रॉपर्टी सहायक।",
        "greeting_evening": "शुभ संध्या! मैं {bot} हूँ, प्राइकून्स का प्रॉपर्टी सहायक।",
        "greeting_late_night": "नमस्ते, इतनी रात तक जाग रहे हैं! मैं {bot} हूँ, प्राइकून्स का प्रॉपर्टी सहायक।",
        "greeting_holiday": "{holiday} की शुभकामनाएँ! मैं {bot} हूँ, प्राइकून्स का प्रॉपर्टी सहायक।",
        "greeting_weather": "{city} में आज मौसम अच्छा है — {weather}।",
        "greeting_weather_bad": "{city} में आज {weather} है, घर से ही विकल्प देखने का अच्छा समय है।",
        "ask_intent": "आप घर खरीदना चाहते हैं, किराए पर लेना चाहते हैं, या केवल विकल्प देखना चाहते हैं?",
        "engagement_tea": "वैसे — चाय या कॉफ़ी?",
        "engagement_weekend": "और वीकेंड आमतौर पर कैसे बिताते हैं?",
        "ask_location": "आप किस इलाके में देख रहे हैं? जैसे अंबली, बोपल, सैटेलाइट या एसजी हाईवे।",
        "ask_type": "आपको किस प्रकार की प्रॉपर्टी चाहिए — अपार्टमेंट, विला या प्लॉट?",
        "ask_bhk": "आपको कितने बेडरूम चाहिए — 2, 3 या 4 बीएचके?",
        "ask_budget": "आपका बजट क्या है? मोटा अनुमान भी चलेगा।",
        "ask_budget_rent": "और मासिक किराया कितना ठीक रहेगा?",
        "ask_amenities": "कोई ज़रूरी सुविधा — पूल, जिम, पार्किंग, बगीचा?",
        "ask_timeline": "आप जल्दी शिफ्ट होना चाहते हैं या कुछ समय बाद?",
        "ask_purpose": "सही सुझाव देने के लिए — यह परिवार के लिए है या निवेश के लिए?",
        "ack": "समझ गया — {details}. ",
        "shortlist_one": "आपकी ज़रूरत से मेल खाता एक विकल्प {verb}:",
        "shortlist_many": "आपकी ज़रूरत से मेल खाते {count} विकल्प {verb}:",
        "verb_sale": "बिक्री के लिए",
        "verb_rent": "किराये पर",
        "shortlist_followup": "किसके बारे में और जानना चाहेंगे? मैं इन्हें और भी छाँट सकता हूँ।",
        "no_match_area": "{area} में {criteria} नहीं मिला, लेकिन ये सबसे नज़दीकी विकल्प हैं:",
        "no_match": "इन शर्तों से मेल खाता कोई विकल्प अभी उपलब्ध नहीं है। मैं क्षेत्र या बजट बढ़ा सकता हूँ, या सलाहकार से नए विकल्प मँगवा सकता हूँ।",
        "advisor_offer": "क्या आप चाहेंगे कि सलाहकार उपलब्धता जाँचकर ब्रोशर भेजें? मैं कॉल भी तय कर सकता हूँ।",
        "widen_offer": "क्या मैं खोज बढ़ाऊँ, या सलाहकार से आने वाले विकल्प जँचवाऊँ?",
        "browse_intro": "अभी उपलब्ध विकल्पों पर एक नज़र:",
        "browse_hint": "इलाका या बजट बताएँ तो मैं इसे और छोटा कर दूँगा।",
        "detail_mock": "(यह डेमो डेटा है, वास्तविक लिस्टिंग नहीं।)",
        "lead_start": "बिल्कुल। सलाहकार किस नाम से बात करें?",
        "lead_ask_phone": "धन्यवाद, {name}. आपका फ़ोन नंबर क्या है?",
        "lead_ask_email": "ठीक है। ब्रोशर के लिए ईमेल? न चाहें तो 'skip' लिखें।",
        "lead_ask_contact": "अंतिम — आप फ़ोन, व्हाट्सएप या ईमेल, किससे संपर्क पसंद करेंगे?",
        "lead_phone_invalid": "नंबर पूरा नहीं लग रहा — 10 अंकों का मोबाइल नंबर बताएँ।",
        "lead_email_invalid": "ईमेल ठीक नहीं लग रहा — जाँचें या 'skip' लिखें।",
        "lead_done": "सब तैयार, {name}. मैंने आपकी जानकारी प्राइकून्स टीम को भेज दी है — वे {contact} पर {phone} पर संपर्क करेंगे।",
        "lead_done_email": " ब्रोशर {email} पर भेजा जाएगा।",
        "lead_done_end": "इस बीच कुछ और जानना चाहेंगे?",
        "handoff": "बिल्कुल। मैं यह बातचीत मानव सलाहकार के लिए चिह्नित कर रहा हूँ, प्राइकून्स टीम जल्द संपर्क करेगी।\n\nकॉलबैक चाहिए तो अपना नंबर और सुविधाजनक समय बता दें।",
        "lead_declined": "कोई बात नहीं — आप आराम से देखें। किसी विकल्प की जानकारी चाहिए तो बताइए।",
    },
    "gu": {
        "greeting_morning": "સુપ્રભાત! હું {bot} છું, પ્રાઇકૂન્સનો પ્રોપર્ટી સહાયક.",
        "greeting_afternoon": "નમસ્કાર! હું {bot} છું, પ્રાઇકૂન્સનો પ્રોપર્ટી સહાયક.",
        "greeting_evening": "શુભ સાંજ! હું {bot} છું, પ્રાઇકૂન્સનો પ્રોપર્ટી સહાયક.",
        "greeting_late_night": "નમસ્તે, આટલી રાત સુધી જાગો છો! હું {bot} છું, પ્રાઇકૂન્સનો પ્રોપર્ટી સહાયક.",
        "greeting_holiday": "{holiday} ની શુભેચ્છા! હું {bot} છું, પ્રાઇકૂન્સનો પ્રોપર્ટી સહાયક.",
        "greeting_weather": "{city} માં આજે મોસમ સરસ છે — {weather}.",
        "greeting_weather_bad": "{city} માં આજે {weather} છે, ઘરેથી વિકલ્પ જોવાનો સારો સમય છે.",
        "ask_intent": "તમે ઘર ખરીદવા માંગો છો, ભાડે લેવા માંગો છો, કે ફક્ત વિકલ્પો જોવા માંગો છો?",
        "engagement_tea": "બને તો — ચા કે કોફી?",
        "engagement_weekend": "અને વીકએન્ડ સામાન્ય રીતે કેવી રીતે પસાર થાય છે?",
        "ask_location": "તમે કયા વિસ્તારમાં જોઈ રહ્યા છો? જેમ કે અંબલી, બોપલ, સેટેલાઇટ કે એસજી હાઈવે.",
        "ask_type": "તમને કેવો પ્રોપર્ટી જોઈએ છે — એપાર્ટમેન્ટ, વિલા કે પ્લોટ?",
        "ask_bhk": "તમને કેટલા બેડરૂમ જોઈએ — 2, 3 કે 4 બીએચકે?",
        "ask_budget": "તમારું બજેટ કેટલું છે? અંદાજ પણ ચાલશે.",
        "ask_budget_rent": "અને માસિક ભાડું કેટલું ઠીક રહેશે?",
        "ask_amenities": "કોઈ જરૂરી સુવિધા — પૂલ, જિમ, પાર્કિંગ, બગીચો?",
        "ask_timeline": "તમે જલદી શિફ્ટ થવા માંગો છો કે થોડા સમય પછી?",
        "ask_purpose": "યોગ્ય સૂચન આપવા — આ પરિવાર માટે છે કે રોકાણ માટે?",
        "ack": "સમજ્યો — {details}. ",
        "shortlist_one": "તમારી જરૂરિયાત મુજબનો એક વિકલ્પ {verb}:",
        "shortlist_many": "તમારી જરૂરિયાત મુજબના {count} વિકલ્પો {verb}:",
        "verb_sale": "વેચાણ માટે",
        "verb_rent": "ભાડા પર",
        "shortlist_followup": "કોના વિશે વધુ જાણવું છે? હું આને વધુ ચોક્કસ કરી શકું છું.",
        "no_match_area": "{area} માં {criteria} મળ્યું નહીં, પરંતુ આ સૌથી નજીકના વિકલ્પો છે:",
        "no_match": "આ શરતો સાથે મેળ ખાતો વિકલ્પ હાલ નથી. હું વિસ્તાર કે બજેટ વધારી શકું, અથવા સલાહકાર પાસે નવા વિકલ્પો મંગાવી શકું.",
        "advisor_offer": "શું તમે ઇચ્છો છો કે સલાહકાર ઉપલબ્ધતા ચકાસી બ્રોશર મોકલે? હું કૉલ પણ ગોઠવી શકું.",
        "widen_offer": "શું હું શોધ વધારું, કે સલાહકાર પાસે આવનારા વિકલ્પો ચકાસાવું?",
        "browse_intro": "હાલ ઉપલબ્ધ વિકલ્પો પર એક નજર:",
        "browse_hint": "વિસ્તાર કે બજેટ જણાવો તો હું આને વધુ ચોક્કસ કરી દઉં.",
        "detail_mock": "(આ ડેમો ડેટા છે, વાસ્તવિક લિસ્ટિંગ નથી.)",
        "lead_start": "ચોક્કસ. સલાહકાર કયા નામે વાત કરે?",
        "lead_ask_phone": "આભાર, {name}. તમારો ફોન નંબર શું છે?",
        "lead_ask_email": "ઠીક છે. બ્રોશર માટે ઈમેલ? ન જોઈએ તો 'skip' લખો.",
        "lead_ask_contact": "છેલ્લું — તમે ફોન, વોટ્સએપ કે ઈમેલ, કોના દ્વારા સંપર્ક ઈચ્છો છો?",
        "lead_phone_invalid": "નંબર પૂરો લાગતો નથી — 10 અંકનો મોબાઈલ નંબર આપો.",
        "lead_email_invalid": "ઈમેલ યોગ્ય લાગતું નથી — ચકાસો અથવા 'skip' લખો.",
        "lead_done": "બધું તૈયાર, {name}. મેં તમારી માહિતી પ્રાઇકૂન્સ ટીમને મોકલી છે — તેઓ {contact} પર {phone} પર સંપર્ક કરશે.",
        "lead_done_email": " બ્રોશર {email} પર મોકલાશે.",
        "lead_done_end": "આ દરમિયાન બીજું કંઈ જાણવું છે?",
        "handoff": "ચોક્કસ. હું આ વાતચીત માનવ સલાહકાર માટે ચિહ્નિત કરું છું, પ્રાઇકૂન્સ ટીમ ટૂંક સમયમાં સંપર્ક કરશે.\n\nકૉલબેક જોઈએ તો નંબર અને અનુકૂળ સમય જણાવો.",
        "lead_declined": "કોઈ વાંધો નહીં — તમે નિરાંતે જુઓ. કોઈ વિકલ્પની માહિતી જોઈએ તો કહો.",
    },
    "mr": {
        "greeting_morning": "सुप्रभात! मी {bot} आहे, प्राइकून्सचा प्रॉपर्टी सहाय्यक.",
        "greeting_afternoon": "नमस्कार! मी {bot} आहे, प्राइकून्सचा प्रॉपर्टी सहाय्यक.",
        "greeting_evening": "शुभ संध्याकाळ! मी {bot} आहे, प्राइकून्सचा प्रॉपर्टी सहाय्यक.",
        "greeting_late_night": "नमस्कार, इतक्या रात्रीपर्यंत जागे आहात! मी {bot} आहे, प्राइकून्सचा प्रॉपर्टी सहाय्यक.",
        "greeting_holiday": "{holiday} च्या शुभेच्छा! मी {bot} आहे, प्राइकून्सचा प्रॉपर्टी सहाय्यक.",
        "greeting_weather": "{city} मध्ये आज हवामान छान आहे — {weather}.",
        "greeting_weather_bad": "{city} मध्ये आज {weather} आहे, घरून पर्याय पाहण्याची चांगली वेळ आहे.",
        "ask_intent": "तुम्हाला घर खरेदी करायचे आहे, भाड्याने घ्यायचे आहे, की फक्त पर्याय पाहायचे आहेत?",
        "engagement_tea": "तसे — चहा की कॉफी?",
        "engagement_weekend": "आणि वीकेंड सहसा कसा जातो?",
        "ask_location": "तुम्ही कोणत्या भागात पाहत आहात? उदा. अंबली, बोपल, सॅटेलाइट किंवा एसजी हायवे.",
        "ask_type": "तुम्हाला कोणत्या प्रकारची मालमत्ता हवी आहे — अपार्टमेंट, व्हिला की प्लॉट?",
        "ask_bhk": "तुम्हाला किती बेडरूम हवे — 2, 3 की 4 बीएचके?",
        "ask_budget": "तुमचे बजेट किती आहे? अंदाजही चालेल.",
        "ask_budget_rent": "आणि मासिक भाडे किती ठीक राहील?",
        "ask_amenities": "काही आवश्यक सुविधा — पूल, जिम, पार्किंग, बाग?",
        "ask_timeline": "तुम्हाला लवकर शिफ्ट व्हायचे आहे की काही काळानंतर?",
        "ask_purpose": "योग्य सूचना देण्यासाठी — हे कुटुंबासाठी आहे की गुंतवणुकीसाठी?",
        "ack": "समजले — {details}. ",
        "shortlist_one": "तुमच्या गरजेशी जुळणारा एक पर्याय {verb}:",
        "shortlist_many": "तुमच्या गरजेशी जुळणारे {count} पर्याय {verb}:",
        "verb_sale": "विक्रीसाठी",
        "verb_rent": "भाड्याने",
        "shortlist_followup": "कोणाबद्दल अधिक जाणून घ्यायचे? मी हे अधिक नेमके करू शकतो.",
        "no_match_area": "{area} मध्ये {criteria} मिळाले नाही, पण हे सर्वात जवळचे पर्याय आहेत:",
        "no_match": "या अटींशी जुळणारा पर्याय सध्या उपलब्ध नाही. मी भाग किंवा बजेट वाढवू शकतो, किंवा सल्लागाराकडून नवीन पर्याय मागवू शकतो.",
        "advisor_offer": "सल्लागार उपलब्धता तपासून ब्रोशर पाठवावा असे वाटते का? मी कॉलही ठरवू शकतो.",
        "widen_offer": "मी शोध वाढवू, की सल्लागाराकडून येणारे पर्याय तपासावे?",
        "browse_intro": "सध्या उपलब्ध पर्यायांवर एक नजर:",
        "browse_hint": "भाग किंवा बजेट सांगा, मी हे अधिक नेमके करतो.",
        "detail_mock": "(हा डेमो डेटा आहे, प्रत्यक्ष लिस्टिंग नाही.)",
        "lead_start": "नक्की. सल्लागार कोणत्या नावाने बोलावे?",
        "lead_ask_phone": "धन्यवाद, {name}. तुमचा फोन नंबर काय आहे?",
        "lead_ask_email": "ठीक आहे. ब्रोशरसाठी ईमेल? नको असल्यास 'skip' लिहा.",
        "lead_ask_contact": "शेवटचे — तुम्हाला फोन, व्हॉट्सअॅप की ईमेल, कशाने संपर्क हवा?",
        "lead_phone_invalid": "नंबर पूर्ण वाटत नाही — 10 अंकी मोबाइल नंबर द्या.",
        "lead_email_invalid": "ईमेल बरोबर वाटत नाही — तपासा किंवा 'skip' लिहा.",
        "lead_done": "सर्व तयार, {name}. मी तुमची माहिती प्राइकून्स टीमला दिली आहे — ते {contact} वर {phone} वर संपर्क करतील.",
        "lead_done_email": " ब्रोशर {email} वर पाठवले जाईल.",
        "lead_done_end": "यादरम्यान अजून काही जाणून घ्यायचे आहे?",
        "handoff": "नक्की. मी ही चर्चा मानवी सल्लागारासाठी चिन्हांकित करत आहे, प्राइकून्स टीम लवकरच संपर्क करेल.\n\nकॉलबॅक हवा असल्यास नंबर आणि सोयीची वेळ सांगा.",
        "lead_declined": "काही हरकत नाही — तुम्ही निवांत पाहा. कोणत्याही पर्यायाची माहिती हवी असल्यास सांगा.",
    },
}


# Labels used inside generated property lines.
_AMENITY_LABELS = {"en": "Amenities", "hi": "सुविधाएँ", "gu": "સુવિધાઓ", "mr": "सुविधा"}
for _lang, _label in _AMENITY_LABELS.items():
    MESSAGES[_lang]["amenities_label"] = _label

# One refusal sentence per language, so a "no answer" reply is never half-translated and always
# recognisable by the citation filter.
_REFUSALS = {
    "en": (
        "I do not have enough information in my knowledge base to answer this question "
        "accurately. Please contact our support team or reach out to a human advisor for "
        "further assistance."
    ),
    "hi": (
        "मेरे ज्ञान आधार में इस प्रश्न का सटीक उत्तर देने के लिए पर्याप्त जानकारी नहीं है। "
        "कृपया हमारी सहायता टीम या मानव सलाहकार से संपर्क करें।"
    ),
    "gu": (
        "મારા જ્ઞાન આધારમાં આ પ્રશ્નનો સચોટ જવાબ આપવા પૂરતી માહિતી નથી. "
        "કૃપા કરીને અમારી સહાય ટીમ અથવા માનવ સલાહકારનો સંપર્ક કરો."
    ),
    "mr": (
        "माझ्या ज्ञानकोशात या प्रश्नाचे अचूक उत्तर देण्यासाठी पुरेशी माहिती नाही. "
        "कृपया आमच्या सहाय्य संघाशी किंवा मानवी सल्लागाराशी संपर्क करा."
    ),
}
for _lang, _text in _REFUSALS.items():
    MESSAGES[_lang]["refusal"] = _text

REFUSAL_TEXTS = {text.strip() for text in _REFUSALS.values()}


def is_refusal(text: str | None) -> bool:
    """
    True when a reply is one of the canonical refusal sentences.

    Compared case-insensitively: models occasionally return the sentence lowercased, and an
    exact-match check then treated a refusal as a grounded answer and attached citations.
    """
    if not text:
        return False
    normalised = " ".join(text.split()).lower()
    return normalised in {item.lower() for item in REFUSAL_TEXTS}


def translate(language: str | None, key: str, **kwargs) -> str:
    """Look up a message in the requested language, falling back to English then the key."""
    lang = language if language in MESSAGES else DEFAULT_LANGUAGE
    template = MESSAGES.get(lang, {}).get(key) or MESSAGES[DEFAULT_LANGUAGE].get(key)
    if template is None:
        return key
    return template.format(**kwargs) if kwargs else template

# Industry-neutral greeting variants. The time-of-day greetings in MESSAGES above are written
# for the Prycoons real-estate bot; every other industry uses these instead so an FMCG bot never
# introduces itself as a property assistant.
_GENERIC_GREETINGS = {
    "en": {
        "morning": "Good morning! I am {bot}.",
        "afternoon": "Good afternoon! I am {bot}.",
        "evening": "Good evening! I am {bot}.",
        "late_night": "Hello — I am {bot}. You are up late; happy to help whenever you are ready.",
    },
    "hi": {
        "morning": "सुप्रभात! मैं {bot} हूँ।",
        "afternoon": "नमस्कार! मैं {bot} हूँ।",
        "evening": "शुभ संध्या! मैं {bot} हूँ।",
        "late_night": "नमस्ते — मैं {bot} हूँ। इतनी रात तक जाग रहे हैं, बताइए कैसे मदद करूँ?",
    },
    "gu": {
        "morning": "સુપ્રભાત! હું {bot} છું.",
        "afternoon": "નમસ્તે! હું {bot} છું.",
        "evening": "શુભ સાંજ! હું {bot} છું.",
        "late_night": "નમસ્તે — હું {bot} છું. રાત સુધી જાગી રહ્યા છો, કહો શું મદદ કરું?",
    },
    "mr": {
        "morning": "सुप्रभात! मी {bot} आहे.",
        "afternoon": "नमस्कार! मी {bot} आहे.",
        "evening": "शुभ संध्याकाळ! मी {bot} आहे.",
        "late_night": "नमस्कार — मी {bot} आहे. रात्री उशिरापर्यंत जागे आहात, सांगा काय मदत करू?",
    },
}

_ASK_INTENT_GENERAL = {
    "en": "How can I help you today?",
    "hi": "आज मैं आपकी कैसे मदद कर सकता हूँ?",
    "gu": "આજે હું તમને કેવી રીતે મદદ કરી શકું?",
    "mr": "आज मी तुम्हाला कशी मदत करू शकतो?",
}

for _lang, _variants in _GENERIC_GREETINGS.items():
    for _part, _text in _variants.items():
        MESSAGES[_lang][f"greeting_{_part}_general"] = _text
    MESSAGES[_lang]["ask_intent_general"] = _ASK_INTENT_GENERAL[_lang]

# One short, friendly opening question. Used for every industry and language; the greeting
# itself stays a single line so the first message is not a questionnaire.
_WELCOME_QUESTIONS = {
    "en": "What can I do for you today?",
    "hi": "मैं आपकी क्या सहायता कर सकता हूँ?",
    "gu": "હું આપની શું મદદ કરી શકું?",
    "mr": "मी आपली काय मदत करू शकतो?",
}
for _lang, _question in _WELCOME_QUESTIONS.items():
    MESSAGES[_lang]["welcome_question"] = _question

_OPENINGS = {
    "en": "Welcome to the chat!",
    "hi": "चैट में आपका स्वागत है!",
    "gu": "ચેટમાં આપનું સ્વાગત છે!",
    "mr": "चॅटमध्ये आपले स्वागत आहे!",
}
for _lang, _text in _OPENINGS.items():
    MESSAGES[_lang]["welcome_opening"] = _text
