import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Real Estate CRM Assistant", page_icon="🏢", layout="wide")

DB_PATH = Path("real_estate_crm.db")


# ==============================
# Database
# ==============================
def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            lead_name TEXT,
            contact_info TEXT,
            source_platform TEXT,
            property_interest TEXT,
            budget TEXT,
            preferred_location TEXT,
            buyer_type TEXT,
            status TEXT,
            last_action TEXT,
            next_follow_up_date TEXT,
            notes TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            lead_id INTEGER,
            lead_name TEXT,
            platform TEXT,
            user_message TEXT NOT NULL,
            assistant_reply TEXT NOT NULL,
            intent TEXT,
            stage TEXT,
            notes_json TEXT,
            FOREIGN KEY (lead_id) REFERENCES leads(id)
        )
        """
    )

    conn.commit()
    conn.close()


# ==============================
# Intent + stage detection
# ==============================
def detect_intent(message: str) -> str:
    msg = message.lower()
    if any(word in msg for word in ["price", "budget", "monthly", "downpayment", "payment", "installment"]):
        return "pricing"
    if any(word in msg for word in ["invest", "investment", "roi", "rental", "appreciation"]):
        return "investment"
    if any(word in msg for word in ["location", "where", "manila", "pasig", "taguig", "qc", "quezon city", "makati", "bgc"]):
        return "location"
    if any(word in msg for word in ["condo", "house", "townhouse", "unit", "property"]):
        return "property_type"
    if any(word in msg for word in ["visit", "viewing", "schedule", "tour", "site tripping"]):
        return "viewing"
    if any(word in msg for word in ["reserve", "reservation", "book"]):
        return "reservation"
    return "general_inquiry"


def detect_stage(message: str) -> str:
    msg = message.lower()
    if any(word in msg for word in ["hello", "hi", "interested", "inquire", "details"]):
        return "new_lead"
    if any(word in msg for word in ["budget", "price", "location", "condo", "house"]):
        return "qualification"
    if any(word in msg for word in ["send", "options", "recommend", "available"]):
        return "options_stage"
    if any(word in msg for word in ["visit", "schedule", "viewing", "tour"]):
        return "viewing_stage"
    if any(word in msg for word in ["reserve", "book"]):
        return "closing_stage"
    return "conversation"


def map_stage_to_status(stage: str) -> str:
    mapping = {
        "new_lead": "New Lead",
        "qualification": "Qualified",
        "options_stage": "Options Sent",
        "viewing_stage": "Site Viewing Scheduled",
        "closing_stage": "Reserved",
        "conversation": "Follow-Up Needed",
    }
    return mapping.get(stage, "New Lead")


def suggest_follow_up(intent: str, stage: str) -> str:
    if intent == "general_inquiry":
        return "Ask whether the buyer is purchasing for investment or personal use."
    if intent == "pricing":
        return "Ask for budget range and preferred payment terms."
    if intent == "investment":
        return "Ask for target location, budget, and expected use case."
    if intent == "location":
        return "Recommend 2–3 suitable areas based on budget and property type."
    if intent == "viewing":
        return "Confirm preferred schedule, contact number, and viewing format."
    if intent == "reservation":
        return "Confirm unit choice, buyer details, and reservation requirements."
    if stage == "closing_stage":
        return "Move toward a concrete next step like reservation or viewing."
    return "Continue qualifying the lead before recommending a property."


def default_follow_up_date(stage: str) -> str:
    days_map = {
        "new_lead": 1,
        "qualification": 1,
        "options_stage": 3,
        "viewing_stage": 1,
        "closing_stage": 1,
        "conversation": 3,
    }
    days = days_map.get(stage, 3)
    return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")


# ==============================
# Chatbot engine
# ==============================
def generate_reply(message: str, agent_name: str, project_name: str, focus_market: str, brand_tone: str, cta_style: str) -> dict:
    intent = detect_intent(message)
    stage = detect_stage(message)

    base_intro = f"Hi! Thanks for your message. This is {agent_name}."

    replies = {
        "general_inquiry": (
            f"{base_intro} I'd be happy to help you with {project_name}. "
            f"Are you looking for a property for investment or personal use? "
            f"You can also share your preferred budget and location so I can recommend the best options for you."
        ),
        "pricing": (
            f"{base_intro} I'd be glad to help with pricing details for {project_name}. "
            f"To recommend the best unit options, may I know your target budget range and whether you're open to monthly payment terms? "
            f"Once I have that, I can suggest the most suitable choices for {focus_market}."
        ),
        "investment": (
            f"{base_intro} Great choice—many buyers consider this a strong opportunity for {focus_market.lower()}. "
            f"If you're buying for investment, I can help you compare location potential, target market fit, and value growth. "
            f"May I know your budget and preferred area so I can narrow down the best options?"
        ),
        "location": (
            f"{base_intro} Location is one of the most important factors when choosing a property. "
            f"For {focus_market.lower()}, I can recommend areas based on convenience, accessibility, and long-term value. "
            f"Which city or area are you considering, and are you looking for condo, house and lot, or townhouse options?"
        ),
        "property_type": (
            f"{base_intro} I can help you compare the right property type based on your goal. "
            f"For example, condos are often ideal for city living and rental potential, while house and lot options suit growing families and end-users. "
            f"Are you buying for investment or personal use, and what budget range do you have in mind?"
        ),
        "viewing": (
            f"{base_intro} Yes, we can help arrange a viewing or site visit. "
            f"Please share your preferred date and time, and whether you want an on-site viewing or an online presentation first. "
            f"I'll help coordinate the next steps for you."
        ),
        "reservation": (
            f"{base_intro} I'd be happy to guide you through the reservation process. "
            f"Before we proceed, may I confirm your preferred unit type, budget range, and contact details? "
            f"Once confirmed, I can help you with the next steps right away."
        ),
    }

    reply = replies[intent]

    if brand_tone == "Luxury":
        reply += " We focus on delivering a polished and premium client experience from inquiry to turnover."
    elif brand_tone == "Friendly":
        reply += " No worries—I’ll keep everything simple and guide you step by step."
    elif brand_tone == "Investment-Focused":
        reply += " I can also help highlight which options may offer stronger long-term value and investor appeal."

    if cta_style == "Soft CTA":
        reply += " When you're ready, send me your budget and preferred location and I'll prepare a few options for you."
    elif cta_style == "Direct CTA":
        reply += " Send me your budget and preferred location now so I can recommend the best matches immediately."
    else:
        reply += " Once I have your goal, budget, and location preference, I can tailor the next recommendations for you."

    return {
        "reply": reply,
        "analysis": {
            "intent": intent,
            "stage": stage,
            "status": map_stage_to_status(stage),
            "budget_needed": intent in ["general_inquiry", "pricing", "investment", "property_type"],
            "location_needed": intent in ["general_inquiry", "pricing", "investment", "location", "property_type"],
            "follow_up_suggestion": suggest_follow_up(intent, stage),
            "next_follow_up_date": default_follow_up_date(stage),
        },
    }


# ==============================
# Lead + chat persistence
# ==============================
def create_lead(lead_name: str, contact_info: str, source_platform: str, property_interest: str, budget: str, preferred_location: str, buyer_type: str, status: str, last_action: str, next_follow_up_date: str, notes: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO leads (
            created_at, lead_name, contact_info, source_platform, property_interest,
            budget, preferred_location, buyer_type, status, last_action,
            next_follow_up_date, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            lead_name,
            contact_info,
            source_platform,
            property_interest,
            budget,
            preferred_location,
            buyer_type,
            status,
            last_action,
            next_follow_up_date,
            notes,
        ),
    )
    lead_id = cur.lastrowid
    conn.commit()
    conn.close()
    return lead_id


def update_lead(lead_id: int, status: str, last_action: str, next_follow_up_date: str, notes: str, budget: str = "", preferred_location: str = "", property_interest: str = "", buyer_type: str = "") -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE leads
        SET status = ?,
            last_action = ?,
            next_follow_up_date = ?,
            notes = ?,
            budget = CASE WHEN ? != '' THEN ? ELSE budget END,
            preferred_location = CASE WHEN ? != '' THEN ? ELSE preferred_location END,
            property_interest = CASE WHEN ? != '' THEN ? ELSE property_interest END,
            buyer_type = CASE WHEN ? != '' THEN ? ELSE buyer_type END
        WHERE id = ?
        """,
        (
            status,
            last_action,
            next_follow_up_date,
            notes,
            budget, budget,
            preferred_location, preferred_location,
            property_interest, property_interest,
            buyer_type, buyer_type,
            lead_id,
        ),
    )
    conn.commit()
    conn.close()


def save_chat(lead_id: int | None, lead_name: str, platform: str, user_message: str, assistant_reply: str, intent: str, stage: str, notes: dict) -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO chat_logs (
            created_at, lead_id, lead_name, platform, user_message, assistant_reply, intent, stage, notes_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            lead_id,
            lead_name,
            platform,
            user_message,
            assistant_reply,
            intent,
            stage,
            json.dumps(notes, ensure_ascii=False),
        ),
    )
    conn.commit()
    conn.close()


def load_leads(limit: int = 50) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM leads ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def load_recent_chats(limit: int = 20) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM chat_logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ==============================
# UI
# ==============================
init_db()

st.title("🏢 Real Estate CRM Assistant")
st.caption("Chatbot + lead tracker in one app. Generate replies, save conversations, and update leads automatically.")

with st.sidebar:
    st.header("Agent Settings")
    agent_name = st.text_input("Agent / Promoter name", value="Ken")
    project_name = st.text_input("Project / Brand name", value="Your Featured Property")
    focus_market = st.selectbox(
        "Focus market",
        ["OFW buyers", "young professionals", "growing families", "investors", "luxury buyers", "first-time buyers"],
    )
    brand_tone = st.selectbox("Brand tone", ["Professional", "Friendly", "Luxury", "Investment-Focused"])
    cta_style = st.selectbox("CTA style", ["Balanced CTA", "Soft CTA", "Direct CTA"])

chat_tab, leads_tab, history_tab = st.tabs(["Chat Assistant", "Lead Tracker", "Chat History"])

with chat_tab:
    left, right = st.columns([1.1, 0.9])

    with left:
        st.subheader("Incoming Inquiry")
        lead_name = st.text_input("Lead name", placeholder="Ex: Maria Santos")
        contact_info = st.text_input("Contact info", placeholder="Messenger, WhatsApp, mobile, or email")
        platform = st.selectbox("Platform", ["Facebook", "Instagram", "TikTok", "Messenger", "WhatsApp", "Email", "Other"])
        buyer_type = st.selectbox("Buyer type", ["Unknown", "Investor", "End User", "OFW", "Luxury Buyer", "First-Time Buyer"])
        property_interest = st.text_input("Property interest", placeholder="Ex: 1BR condo, townhouse, house and lot")
        budget = st.text_input("Budget", placeholder="Ex: ₱4M to ₱6M")
        preferred_location = st.text_input("Preferred location", placeholder="Ex: Pasig, Taguig, Manila")
        incoming_message = st.text_area(
            "Incoming buyer message",
            placeholder="Ex: Hi, I'm interested in your condo in Manila. Can you send the price and monthly payment details?",
            height=180,
        )
        save_as_new = st.checkbox("Create a new lead automatically", value=True)
        generate = st.button("Generate Reply + Save", type="primary")

    with right:
        st.subheader("How this works")
        st.write(
            "Each inquiry can create or update a lead, generate a reply, assign a pipeline status, and schedule the next follow-up date."
        )
        st.markdown(
            """
            **Automatic actions:**
            - detects intent
            - detects sales stage
            - suggests a reply
            - assigns lead status
            - schedules next follow-up
            - stores chat history
            """
        )

    if generate:
        if not incoming_message.strip():
            st.error("Please enter the buyer's message first.")
        else:
            result = generate_reply(
                message=incoming_message,
                agent_name=agent_name,
                project_name=project_name,
                focus_market=focus_market,
                brand_tone=brand_tone,
                cta_style=cta_style,
            )
            reply = result["reply"]
            analysis = result["analysis"]

            last_action = f"Chatbot reply generated from {platform} inquiry"
            notes = analysis["follow_up_suggestion"]

            lead_id = None
            if save_as_new:
                lead_id = create_lead(
                    lead_name=lead_name,
                    contact_info=contact_info,
                    source_platform=platform,
                    property_interest=property_interest,
                    budget=budget,
                    preferred_location=preferred_location,
                    buyer_type=buyer_type,
                    status=analysis["status"],
                    last_action=last_action,
                    next_follow_up_date=analysis["next_follow_up_date"],
                    notes=notes,
                )

            save_chat(
                lead_id=lead_id,
                lead_name=lead_name,
                platform=platform,
                user_message=incoming_message,
                assistant_reply=reply,
                intent=analysis["intent"],
                stage=analysis["stage"],
                notes=analysis,
            )

            st.success("Reply generated and saved. Lead tracker updated.")

            a, b = st.columns([1.35, 0.65])
            with a:
                st.markdown("### Suggested Reply")
                st.text_area("Reply", value=reply, height=260)
                st.download_button("Download Reply", data=reply, file_name="real_estate_reply.txt", mime="text/plain")
            with b:
                st.markdown("### Lead Analysis")
                st.write(f"**Intent:** {analysis['intent']}")
                st.write(f"**Stage:** {analysis['stage']}")
                st.write(f"**Auto status:** {analysis['status']}")
                st.write(f"**Next follow-up:** {analysis['next_follow_up_date']}")
                st.info(analysis["follow_up_suggestion"])

with leads_tab:
    st.subheader("Lead Tracker")
    rows = load_leads()

    if not rows:
        st.write("No leads saved yet.")
    else:
        for row in rows:
            title = f"#{row['id']} • {row['lead_name'] or 'Unknown Lead'} • {row['status']} • Follow-up: {row['next_follow_up_date'] or '-'}"
            with st.expander(title):
                st.write(f"**Created:** {row['created_at']}")
                st.write(f"**Contact:** {row['contact_info']}")
                st.write(f"**Platform:** {row['source_platform']}")
                st.write(f"**Property interest:** {row['property_interest']}")
                st.write(f"**Budget:** {row['budget']}")
                st.write(f"**Preferred location:** {row['preferred_location']}")
                st.write(f"**Buyer type:** {row['buyer_type']}")
                st.write(f"**Last action:** {row['last_action']}")
                st.write(f"**Notes:** {row['notes']}")

                new_status = st.selectbox(
                    f"Update status #{row['id']}",
                    ["New Lead", "Qualified", "Options Sent", "Follow-Up Needed", "Site Viewing Scheduled", "Reserved", "Closed Won", "Closed Lost"],
                    index=["New Lead", "Qualified", "Options Sent", "Follow-Up Needed", "Site Viewing Scheduled", "Reserved", "Closed Won", "Closed Lost"].index(row['status']) if row['status'] in ["New Lead", "Qualified", "Options Sent", "Follow-Up Needed", "Site Viewing Scheduled", "Reserved", "Closed Won", "Closed Lost"] else 0,
                    key=f"status_{row['id']}",
                )
                new_followup = st.text_input(
                    f"Next follow-up date #{row['id']}",
                    value=row['next_follow_up_date'] or "",
                    key=f"follow_{row['id']}",
                )
                new_notes = st.text_area(
                    f"Notes #{row['id']}",
                    value=row['notes'] or "",
                    height=90,
                    key=f"notes_{row['id']}",
                )
                if st.button(f"Save Lead Update #{row['id']}"):
                    update_lead(
                        lead_id=row['id'],
                        status=new_status,
                        last_action="Lead manually updated in CRM",
                        next_follow_up_date=new_followup,
                        notes=new_notes,
                    )
                    st.success(f"Lead #{row['id']} updated.")

with history_tab:
    st.subheader("Chat History")
    chats = load_recent_chats()

    if not chats:
        st.write("No chat history yet.")
    else:
        for row in chats:
            notes = json.loads(row["notes_json"] or "{}")
            title = f"{row['created_at']} • {row['platform']} • {row['lead_name'] or 'Unknown Lead'}"
            with st.expander(title):
                st.write(f"**Intent:** {row['intent']}")
                st.write(f"**Stage:** {row['stage']}")
                st.write(f"**Linked lead ID:** {row['lead_id']}")
                st.write("**Buyer message:**")
                st.text_area(f"Buyer message {row['id']}", value=row['user_message'], height=100, key=f"buyer_{row['id']}")
                st.write("**Suggested reply:**")
                st.text_area(f"Reply {row['id']}", value=row['assistant_reply'], height=180, key=f"reply_{row['id']}")
                if notes:
                    st.caption(f"Follow-up suggestion: {notes.get('follow_up_suggestion', '')}")

st.markdown("---")
st.caption("Next upgrades: OpenAI smart replies, duplicate lead detection, WhatsApp/Messenger workflow, dashboard charts, and automated reminders.")