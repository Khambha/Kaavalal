from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/citizen", tags=["Citizen services"])

GUIDANCE = [
    {"keywords": ["flood", "water", "വെള്ളപ്പൊക്കം", "വെള്ളം"], "title": "Flood safety", "answer": "Move to higher ground and avoid walking or driving through floodwater. Switch off electricity only if it is safe. Share your location and the number of people needing help through SOS. Check official alerts and follow evacuation directions."},
    {"keywords": ["landslide", "hill", "slope", "മണ്ണിടിച്ചിൽ", "ചരിവ്"], "title": "Landslide safety", "answer": "Move away from steep slopes, retaining walls, and flowing debris. Watch for new cracks, leaning trees, or unusual sounds. Follow evacuation instructions and do not return until authorities say it is safe."},
    {"keywords": ["shelter", "evacuate", "evacuation", "അഭയകേന്ദ്ര", "ഒഴിപ്പി"], "title": "Finding a shelter", "answer": "Open Find Nearby Shelter to view active locations and available capacity. Submit a household request with a contact number and accessibility needs. The rescue team for that area reviews the request and confirms the assignment."},
    {"keywords": ["sos", "rescue", "emergency", "help", "അടിയന്തര", "സഹായം", "രക്ഷ"], "title": "Requesting emergency help", "answer": "Use Ask for Emergency/SOS Response and include your location, the number of people affected, urgency, and any medical or accessibility needs. Your request is routed to response teams covering that LAC. For immediate life-threatening danger, also contact local emergency services directly."},
    {"keywords": ["alert", "warning", "മുന്നറിയിപ്പ്", "അറിയിപ്പ്"], "title": "Disaster alerts", "answer": "Open View Disaster Alerts for current notices published by administrators. Check the affected district, severity, issue time, and expiry, then follow official instructions."},
    {"keywords": ["first aid", "injury", "medical", "പരിക്ക്", "വൈദ്യ", "ആരോഗ്യം"], "title": "Medical emergency", "answer": "Contact emergency medical services for urgent injuries. If it is safe, stay with the injured person, avoid moving someone with a possible neck or back injury, and share the exact location and immediate needs in your SOS request."},
]

DEFAULT_ANSWER = "I can help with flood and landslide safety, emergency requests, shelters, alerts, and basic preparedness. Tell me which topic you need. For urgent danger, contact local emergency services and use the SOS form to alert the Kaavalal response team."


class ChatQuestion(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    language: str = Field(default="en", pattern="^(en|ml)$")


@router.get("/guidance")
def guidance():
    return [{"title": item["title"], "answer": item["answer"]} for item in GUIDANCE]


@router.post("/chat")
def chat(data: ChatQuestion):
    question = data.question.casefold()
    matched = next((item for item in GUIDANCE if any(keyword in question for keyword in item["keywords"])), None)
    malayalam = {
        "Flood safety": "ഉയർന്ന സ്ഥലത്തേക്ക് മാറുക. വെള്ളപ്പൊക്കത്തിലൂടെ നടക്കുകയോ വാഹനമോടിക്കുകയോ ചെയ്യരുത്. സുരക്ഷിതമാണെങ്കിൽ വൈദ്യുതി ബന്ധം വിച്ഛേദിക്കുക. SOS വഴി നിങ്ങളുടെ സ്ഥലവും സഹായം ആവശ്യമുള്ള ആളുകളുടെ എണ്ണവും അറിയിക്കുക. ഔദ്യോഗിക മുന്നറിയിപ്പുകളും ഒഴിപ്പിക്കൽ നിർദ്ദേശങ്ങളും പാലിക്കുക.",
        "Landslide safety": "കുത്തനെയുള്ള ചരിവുകൾ, മതിലുകൾ, മണ്ണൊഴുക്ക് എന്നിവയിൽ നിന്ന് മാറുക. പുതിയ വിള്ളലുകൾ, ചരിയുന്ന മരങ്ങൾ, അസാധാരണ ശബ്ദങ്ങൾ എന്നിവ ശ്രദ്ധിക്കുക. ഒഴിപ്പിക്കൽ നിർദ്ദേശങ്ങൾ പാലിക്കുക; അധികൃതർ സുരക്ഷിതമെന്ന് അറിയിക്കുന്നതുവരെ മടങ്ങരുത്.",
        "Finding a shelter": "അടുത്തുള്ള അഭയകേന്ദ്രങ്ങൾക്കും ലഭ്യമായ ശേഷിക്കും ‘അടുത്തുള്ള അഭയകേന്ദ്രം കണ്ടെത്തുക’ തുറക്കുക. ബന്ധപ്പെടാനുള്ള നമ്പറും പ്രത്യേക ആവശ്യങ്ങളും നൽകി കുടുംബത്തിനായി അഭ്യർത്ഥിക്കുക. ആ പ്രദേശത്തെ രക്ഷാസംഘം പരിശോധിച്ച് സ്ഥലം സ്ഥിരീകരിക്കും.",
        "Requesting emergency help": "‘അടിയന്തര / SOS സഹായം’ തുറന്ന് നിങ്ങളുടെ സ്ഥലം, ബാധിതരുടെ എണ്ണം, അടിയന്തരത, ആരോഗ്യ അല്ലെങ്കിൽ പ്രവേശന സഹായ ആവശ്യങ്ങൾ എന്നിവ നൽകുക. ആ LAC പരിധിയിലെ രക്ഷാസംഘത്തിന് അഭ്യർത്ഥന ലഭിക്കും. ജീവന് അടിയന്തര ഭീഷണിയുണ്ടെങ്കിൽ ഔദ്യോഗിക അടിയന്തര സേവനങ്ങളെയും ബന്ധപ്പെടുക.",
        "Disaster alerts": "അഡ്മിൻ പ്രസിദ്ധീകരിച്ച നിലവിലെ അറിയിപ്പുകൾ ‘ദുരന്ത മുന്നറിയിപ്പുകൾ’ വിഭാഗത്തിൽ കാണുക. ബാധിത ജില്ല, തീവ്രത, പ്രസിദ്ധീകരിച്ച സമയം, കാലാവധി എന്നിവ പരിശോധിച്ച് ഔദ്യോഗിക നിർദ്ദേശങ്ങൾ പാലിക്കുക.",
        "Medical emergency": "അടിയന്തര പരിക്കുകൾക്ക് അടിയന്തര മെഡിക്കൽ സേവനങ്ങളെ ബന്ധപ്പെടുക. സുരക്ഷിതമാണെങ്കിൽ പരിക്കേറ്റയാളോടൊപ്പം തുടരുക. കഴുത്തിലോ പുറകിലോ പരിക്കുണ്ടെന്ന് സംശയിക്കുന്നയാളെ നീക്കരുത്. കൃത്യമായ സ്ഥലവും ആവശ്യങ്ങളും SOS അഭ്യർത്ഥനയിൽ നൽകുക.",
    };
    answer = matched["answer"] if matched else DEFAULT_ANSWER
    if data.language == "ml":
        answer = malayalam.get(matched["title"], answer) if matched else "വെള്ളപ്പൊക്കം, മണ്ണിടിച്ചിൽ, അടിയന്തര സഹായം, അഭയകേന്ദ്രം, മുന്നറിയിപ്പ്, ദുരന്ത മുന്നൊരുക്കം എന്നിവയെക്കുറിച്ച് ചോദിക്കാം. അടിയന്തര അപകടത്തിൽ ഔദ്യോഗിക അടിയന്തര സേവനങ്ങളെ ബന്ധപ്പെടുകയും SOS അഭ്യർത്ഥന അയയ്ക്കുകയും ചെയ്യുക."
    return {"answer": answer,
            "topic": matched["title"] if matched else "Disaster information",
            "source": "Kaavalal preparedness guidance"}
