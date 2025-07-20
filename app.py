from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/assess', methods=['POST'])
def assess_risk():
    responses = request.get_json()

    ln = calculate_ln(responses)
    la = calculate_la(responses)
    risk = calculate_nitrosamine_risk(responses, ln, la)
    carry_nitrites = "Yes" if ln in ["LN1", "LN2"] else "No"
    carry_amines = "Yes" if la in ["LA1", "LA2"] else "No"
    recommendations = generate_recommendations(risk, carry_nitrites, carry_amines)

    group4_disabled = any((responses.get(f"group1_q{i}") or "").lower() in ["yes", "dont know"] for i in range(1, 6))

    return jsonify({
    "ln": ln,
    "la": la,
    "risk": risk,
    "carryNitrites": carry_nitrites,
    "carryAmines": carry_amines,
    "recommendedActions": recommendations,
    "group4_disabled": group4_disabled  # ✅ Include this for preview placeholder
})


# --- Logic Functions ---

def calculate_ln(data):
    # Group 1 (LN1 / LN2)
    ln = "LN4"
    for i in range(1, 6):
        val = data.get(f"group1_q{i}", "").lower()
        if val == "yes":
            return "LN1"
        elif val == "dont know" and ln != "LN1":
            ln = "LN2"

    # Group 3: Water used + potable = LN3
    if data.get("group3_q1", "").lower() in ["yes", "dont know"] and data.get("group3_q2", "").lower() == "potable":
        if ln not in ["LN1", "LN2"]:
            ln = "LN3"

    # Group 7 Nitrites
    g71 = data.get("group7_q1", "").lower()
    g72 = data.get("group7_q2", "").lower()
    if (
        (g71 == "yes" and g72 == "yes") or
        (g71 == "dont know" and g72 in ["yes", "dont know"])
    ) and ln == "LN4":
        ln = "LN3"

    return ln

def calculate_la(data):
    la_flags = {"LA1": False, "LA2": False, "LA3": False}

    # Group 1 subquestions
    for i in range(1, 6):
        for j in ["_1", "_2"]:
            val = data.get(f"group1_q{i}{j}", "").lower()
            if val == "yes":
                la_flags["LA1"] = True
            elif val == "dont know":
                la_flags["LA2"] = True

    # Group 3 ion-exchange water
    if data.get("group3_q1", "").lower() in ["yes", "dont know"] and data.get("group3_q2", "").lower() == "ion_exchange":
        la_flags["LA3"] = True

    # Group 4
    g4 = data.get("group4_q1", "").lower()
    if g4 == "yes":
        la_flags["LA1"] = True
    elif g4 == "dont know":
        la_flags["LA2"] = True

    # Group 5
    g5 = data.get("group5_q1", "").lower()
    if g5 == "yes":
        la_flags["LA2"] = True
    elif g5 == "dont know":
        la_flags["LA3"] = True

    # Group 6
    g6 = data.get("group6_q1", "").lower()
    if g6 == "yes":
        la_flags["LA2"] = True
    elif g6 == "dont know":
        la_flags["LA3"] = True

    # Group 7
    g71 = data.get("group7_q1", "").lower()
    g72 = data.get("group7_q2", "").lower()
    if (
        (g71 == "yes" and g72 == "yes") or
        (g71 == "dont know" and g72 in ["yes", "dont know"])
    ):
        la_flags["LA3"] = True

    if la_flags["LA1"]:
        return "LA1"
    if la_flags["LA2"]:
        return "LA2"
    if la_flags["LA3"]:
        return "LA3"
    return "LA4"

def calculate_nitrosamine_risk(data, ln, la):
    same_step = any(data.get(f"group1_q{i}_1", "").lower() == "yes" for i in range(1, 6))
    chloramine_water = data.get("group3_q3", "").lower() == "yes"
    chloramine_equip = data.get("group7_q3", "").lower() == "yes"
    g71 = data.get("group7_q1", "").lower()
    g72 = data.get("group7_q2", "").lower()

    # Group 7 rule
    group7_minor = (
        (g71 == "yes" and g72 in ["yes", "dont know"]) or
        (g71 == "dont know" and g72 in ["yes", "dont know"])
    )
    if g72 == "no" or g71 == "no":
        group7_minor = False

    if ln == "LN1" and la == "LA1" and same_step:
        return "high"
    if (
        (ln == "LN1" and la == "LA1") or
        (ln == "LN1" and la == "LA2") or
        (ln == "LN2" and la in ["LA1", "LA2"])
    ):
        return "moderate"
    if (
        (ln == "LN3" and la in ["LA1", "LA2", "LA3"]) or
        (la == "LA3" and ln in ["LN1", "LN2", "LN3"]) or
        group7_minor or
        ((ln == "LN4" and la == "LA4") and (chloramine_water or chloramine_equip))
    ):
        return "minor"
    return "nil"

def generate_recommendations(risk, carry_nitrites, carry_amines):
    actions = "<h2>Recommended Actions Based on Assessment</h2><ul>"

    # Risk-based
    if risk == "high":
        actions += "<li><strong>Nitrosamine Risk (High):</strong> Identify potential nitrosamine impurity and evaluate batches for nitrosamine impurity. Establish scientifically sound specifications for nitrosamines in the excipient such that carryover into the drug product will not cause product failure.</li>"
    elif risk in ["moderate", "minor"]:
        actions += f"<li><strong>Nitrosamine Risk ({risk.capitalize()}):</strong> Identify potential nitrosamine impurity and evaluate batches for nitrosamine impurity. If detectable amounts are observed establish scientifically sound specification limits for the nitrosamines in the excipient such that carryover into the drug product will not cause product failure. If specifications and regular monitoring is not warranted, monitor representative batches annually. No out-of-specification results shall occur or else enhance controls.</li>"
    elif risk == "nil":
        actions += "<li><strong>Nitrosamine Risk (Nil):</strong> No further action required. Document the assessment and perform periodic reassessment.</li>"

    # Carryover
    if carry_nitrites == "Yes":
        actions += "<li><strong>Carryover of Nitrites:</strong> Assess the risk of nitrosamine or NDSRI formation in the drug product due to nitrite carryover.</li>"
    if carry_amines == "Yes":
        actions += "<li><strong>Carryover of Secondary/Tertiary Amines:</strong> Assess the risk of nitrosamine or NDSRI formation in the drug product due to amine carryover.</li>"
    if risk == "nil" and carry_nitrites == "No" and carry_amines == "No":
        actions += "<li><strong>Overall:</strong> No immediate action required.</li>"

    actions += "</ul>"
    return actions

if __name__ == "__main__":
    app.run(debug=True)
