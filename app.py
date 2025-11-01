# backend/app.py
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
import base64
import requests
import os
import logging
import traceback

# ---- App init ----
app = Flask(__name__)
CORS(app)  # allow cross-origin calls (you can restrict origins later)

# ---- Configuration (from env, with your previous defaults) ----
IBM_CLIENT_ID = os.environ.get("IBM_CLIENT_ID", "924726a273f72a75733787680810c4e4")
IBM_CLIENT_SECRET = os.environ.get("IBM_CLIENT_SECRET", "7154c95b3351d88cb31302f297eb5a9c")
X_CHANNEL = os.environ.get("X_CHANNEL", "retailergateway")
PUBLIC_KEY_PATH = os.path.join(os.path.dirname(__file__), "retailergateway.pem")

# ---- Logging ----
logging.basicConfig(level=logging.INFO)

# ---- Load IBM Public Key (PEM) ----
if not os.path.exists(PUBLIC_KEY_PATH):
    app.logger.error("Public key not found at %s", PUBLIC_KEY_PATH)
    raise FileNotFoundError(f"Public key not found at {PUBLIC_KEY_PATH}")

with open(PUBLIC_KEY_PATH, "rb") as f:
    pem_data = f.read()
    public_key = serialization.load_pem_public_key(pem_data)

# ---- Helper: RSA Encrypt using PKCS#1 v1.5 ----
def encrypt_with_ibm_key(plain_text: str) -> str:
    """
    Encrypt with the IBM public key (PKCS#1 v1.5) and return base64 string.
    """
    ciphertext = public_key.encrypt(
        plain_text.encode("utf-8"),
        padding.PKCS1v15()
    )
    return base64.b64encode(ciphertext).decode("utf-8")

# ---- Helper: IBM API Caller using session (no timeout) ----
def call_ibm_api_session(session: requests.Session, url: str, xhash: str, body: dict, extra_headers: dict = None):
    """
    Send a POST to `url` using provided requests.Session (so cookies persist).
    No timeout used (per your request).
    """
    headers = {
        "X-Hash-Value": xhash or "",
        "X-IBM-Client-Id": IBM_CLIENT_ID,
        "X-IBM-Client-Secret": IBM_CLIENT_SECRET,
        "X-Channel": X_CHANNEL,
        "Content-Type": "application/json",
        "accept": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)
    try:
        resp = session.post(url, headers=headers, json=body)  # no timeout
        try:
            return resp.json()
        except Exception:
            return {"http_status": resp.status_code, "text": resp.text}
    except Exception as e:
        return {"error": str(e), "trace": traceback.format_exc()}


# ---- (Optional) Additional permissive CORS headers for preflight handled here too ----
@app.after_request
def add_cors_headers(response):
    # Note: Flask-Cors already sets these; we keep these for compatibility.
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Hash-Value, X-IBM-Client-Id, X-IBM-Client-Secret, X-Channel"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response

# ---- Global Storage ----
# NOTE: This keeps global_xhash as in your original pattern. For multi-user usage consider per-session storage.
global_xhash = None

# ---- API: /api/encrypt ----
@app.route("/api/encrypt", methods=["POST"])
def api_encrypt():
    """
    Receives JSON: { number: "...", pin: "..." }
    - `number` should be like "1010@923355923388" (MPOS@MSISDN).
    - `pure_number` (derived) will be "923355923388" and used inside request bodies as MSISDN/SenderMSISDN etc.
    Performs RSA encrypt (number:pin) -> calls CorporateLogin -> if success, sets global_xhash and calls all provided APIs.
    Returns encrypted value, login result, xHash and additional api results.
    """
    global global_xhash
    try:
        data = request.get_json(force=True)
        number = data.get("number")  # expected format e.g. "1010@923355923388"
        pin = data.get("pin")
        if not number or not pin:
            return jsonify({"error": "number and pin required"}), 400

        # derive pure_number (MSISDN without MPOS)
        if "@" in number:
            pure_number = number.split("@", 1)[1]
        else:
            pure_number = number

        # Create payload and encrypt (LoginPayload)
        payload = f"{number}:{pin}"
        encrypted_value = encrypt_with_ibm_key(payload)

        # Use a session to persist cookies returned by CorporateLogin (curl examples included cookies)
        session = requests.Session()

        # Corporate login
        login_url = "https://rgw.8798-f464fa20.eu-de.ri1.apiconnect.appdomain.cloud/tmfb/dev-catalog/CorporateLogin/"
        login_headers = {
            "X-IBM-Client-Id": IBM_CLIENT_ID,
            "X-IBM-Client-Secret": IBM_CLIENT_SECRET,
            "X-Channel": X_CHANNEL,
            "Content-Type": "application/json",
        }

        try:
            login_resp = session.post(login_url, headers=login_headers, json={"LoginPayload": encrypted_value})
        except Exception as e:
            app.logger.exception("CorporateLogin request failed")
            return jsonify({"error": "CorporateLogin request failed", "details": str(e), "trace": traceback.format_exc()}), 500

        try:
            login_result = login_resp.json()
        except Exception:
            login_result = {"http_status": login_resp.status_code, "text": login_resp.text}

        additional_apis = {}

        # If login success -> set xhash (encrypt User~Timestamp) and call the provided APIs
        if isinstance(login_result, dict) and login_result.get("ResponseCode") == "0":
            user_ts = f"{login_result.get('User')}~{login_result.get('Timestamp')}"
            global_xhash = encrypt_with_ibm_key(user_ts)
            xhash = global_xhash

            # Now call each API from your cURL list. Use pure_number in bodies where only MSISDN is needed.
            # 1) OTCIBFT Inquiry
            try:
                otc_ibft_inquiry_payload = {
                    "Amount": "1",
                    "AccountNumber": "00020000011001325",
                    "BankTitle": "MOD",
                    "SenderCNIC": "3234345675432",
                    "SenderMSISDN": pure_number,
                    "ReceiverMSISDN": "923139282625",
                    "BankShortName": "MOD",
                    "TransactionPurpose": "0350"
                }
                additional_apis["OTCIBFT_Inquiry"] = call_ibm_api_session(
                    session,
                    "https://rgw.8798-f464fa20.eu-de.ri1.apiconnect.appdomain.cloud/tmfb/dev-catalog/OTCIBFT/Inquiry",
                    xhash,
                    otc_ibft_inquiry_payload
                )
            except Exception:
                additional_apis["OTCIBFT_Inquiry"] = {"error": "OTCIBFT Inquiry failed", "trace": traceback.format_exc()}

            # 2) OTCIBFT Transfer
            try:
                otc_ibft_transfer_payload = {
                    "Amount": "1",
                    "AccountNumber": "00020000011005325",
                    "BankTitle": "MOD",
                    "SenderCNIC": "3234345675432",
                    "SenderMSISDN": pure_number,
                    "ReceiverMSISDN": "923139282625",
                    "BankShortName": "MOD",
                    "TransactionPurpose": "0350",
                    "MPOS": number,
                    "QuoteID": "1790704"
                }
                additional_apis["OTCIBFT_Transfer"] = call_ibm_api_session(
                    session,
                    "https://rgw.8798-f464fa20.eu-de.ri1.apiconnect.appdomain.cloud/tmfb/dev-catalog/OTCIBFT/Transfer",
                    xhash,
                    otc_ibft_transfer_payload
                )
            except Exception:
                additional_apis["OTCIBFT_Transfer"] = {"error": "OTCIBFT Transfer failed", "trace": traceback.format_exc()}

            # 3) OTCUtilityBill Inquiry
            try:
                otc_utility_inquiry_payload = {
                    "amount": "2000",
                    "ConsumerNumber": "05131230277449",
                    "SenderMSISDN": pure_number,
                    "SenderCNIC": "3234345675432",
                    "Company": "FESCO"
                }
                additional_apis["OTCUtilityBill_Inquiry"] = call_ibm_api_session(
                    session,
                    "https://rgw.8798-f464fa20.eu-de.ri1.apiconnect.appdomain.cloud/tmfb/dev-catalog/OTCUtilityBill/Inquiry",
                    xhash,
                    otc_utility_inquiry_payload
                )
            except Exception:
                additional_apis["OTCUtilityBill_Inquiry"] = {"error": "OTCUtilityBill Inquiry failed", "trace": traceback.format_exc()}

            # 4) OTCUtilityBill Payment
            try:
                otc_utility_payment_payload = {
                    "Amount": "2000",
                    "ConsumerNumber": "05131230277449",
                    "SenderMSISDN": pure_number,
                    "SenderCNIC": "3234345675432",
                    "Company": "FESCO",
                    "QuoteID": "1790704"
                }
                additional_apis["OTCUtilityBill_Payment"] = call_ibm_api_session(
                    session,
                    "https://rgw.8798-f464fa20.eu-de.ri1.apiconnect.appdomain.cloud/tmfb/dev-catalog/OTCUtilityBill/Payment",
                    xhash,
                    otc_utility_payment_payload
                )
            except Exception:
                additional_apis["OTCUtilityBill_Payment"] = {"error": "OTCUtilityBill Payment failed", "trace": traceback.format_exc()}

            # 5) OTCUtilityBill Payment (repeat as per your curls)
            try:
                additional_apis["OTCUtilityBill_Payment_Repeat"] = call_ibm_api_session(
                    session,
                    "https://rgw.8798-f464fa20.eu-de.ri1.apiconnect.appdomain.cloud/tmfb/dev-catalog/OTCUtilityBill/Payment",
                    xhash,
                    otc_utility_payment_payload
                )
            except Exception:
                additional_apis["OTCUtilityBill_Payment_Repeat"] = {"error": "OTCUtilityBill Payment (repeat) failed", "trace": traceback.format_exc()}

            # 6) CashDeposit
            try:
                cash_deposit_payload = {
                    "Amount": "50",
                    "MSISDN": pure_number,
                    "MPOS": "1010@923355923388"
                }
                # The curl included an MPOS header; include MPOS header too (example)
                extra_headers = {"MPOS": "1111@923355923388"}
                additional_apis["CashDeposit"] = call_ibm_api_session(
                    session,
                    "https://rgw.8798-f464fa20.eu-de.ri1.apiconnect.appdomain.cloud/tmfb/dev-catalog/CashDeposit/CashDeposit",
                    xhash,
                    cash_deposit_payload,
                    extra_headers=extra_headers
                )
            except Exception:
                additional_apis["CashDeposit"] = {"error": "CashDeposit failed", "trace": traceback.format_exc()}

            # 7) CashWithdrawal
            try:
                cash_withdrawal_payload = {
                    "Amount": "5",
                    "MSISDN": "923482665224",
                    "MPOS": "1010@923355923388"
                }
                additional_apis["CashWithdrawal"] = call_ibm_api_session(
                    session,
                    "https://rgw.8798-f464fa20.eu-de.ri1.apiconnect.appdomain.cloud/tmfb/dev-catalog/CashWithdrawal/CashWithdrawal",
                    xhash,
                    cash_withdrawal_payload
                )
            except Exception:
                additional_apis["CashWithdrawal"] = {"error": "CashWithdrawal failed", "trace": traceback.format_exc()}

        else:
            # Login failed or unexpected result - do not attempt further calls
            app.logger.warning("Login failed or returned unexpected result: %s", login_result)

        # Return everything
        return jsonify({
            "encryptedValue": encrypted_value,
            "ibmLoginResult": login_result,
            "xHash": global_xhash,
            "additionalApis": additional_apis,
            "usedNumber": number,
            "pureNumber": pure_number
        })

    except Exception as e:
        app.logger.exception("Encryption or IBM API call failed")
        return jsonify({"error": "Encryption or IBM API call failed", "details": str(e), "trace": traceback.format_exc()}), 500


# ---- Serve index.html directly (dashboard) ----
@app.route("/")
def serve_index():
    # The dashboard HTML is intentionally long; keep HTML embedded as requested.
    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>IBM/RSA RET-API Dashboard</title>
<style>
  /* ---------- Global Styles ---------- */
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background-color: #f4f7f9;
    color: #333;
    line-height: 1.6;
  }
  .container {
    max-width: 1000px;
    margin: 40px auto;
    padding: 20px;
  }
  h1, h2, h3 {
    color: #222;
  }
  h1 { text-align: center; margin-bottom: 30px; }

  /* ---------- Card Sections ---------- */
  .card {
    background: #fff;
    border-radius: 12px;
    padding: 25px 20px;
    margin-bottom: 25px;
    box-shadow: 0 8px 20px rgba(0,0,0,0.08);
    transition: transform 0.2s;
  }
  .card:hover { transform: translateY(-3px); }
  .card h3 { margin-bottom: 15px; }

  /* ---------- Form Styles ---------- */
  label { font-weight: 600; margin-bottom: 5px; display: block; color: #555; }
  input, select, button, textarea {
    width: 100%;
    padding: 12px;
    margin-bottom: 15px;
    border-radius: 8px;
    border: 1px solid #ccc;
    font-size: 14px;
  }
  input:focus, select:focus, textarea:focus { outline: none; border-color: #4a90e2; }
  button {
    background-color: #4a90e2;
    color: white;
    border: none;
    font-weight: 600;
    cursor: pointer;
    transition: 0.2s;
  }
  button:hover { background-color: #357ABD; }

  /* ---------- Response Boxes ---------- */
  .response-box {
    background: #f0f4ff;
    padding: 15px;
    border-radius: 10px;
    margin-top: 10px;
    overflow-x: auto;
  }
  .response-box h4 {
    margin-bottom: 8px;
    font-size: 16px;
    color: #222;
  }
  pre {
    font-family: monospace;
    font-size: 13px;
    white-space: pre-wrap;
    word-break: break-word;
    color: #111;
  }

  /* ---------- Transactions Table ---------- */
  table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 10px;
    font-size: 14px;
  }
  th, td {
    padding: 8px 10px;
    border: 1px solid #ddd;
    text-align: left;
  }
  th {
    background-color: #4a90e2;
    color: white;
  }

  /* ---------- Responsive ---------- */
  @media (max-width: 600px) {
    .container { padding: 10px; }
  }
</style>
</head>
<body>
<div class="container">
  <h1>🔐 IBM/RSA RET-API Dashboard</h1>

  <!-- ---------- Login Section ---------- -->
  <div class="card">
  <h3>1️⃣ Login & Generate X-Hash</h3>

  <label for="numberInput">Number (MPOS@MSISDN)</label>
  <select id="numberInput">
    <option value="1010@923355923388">1010@923355923388</option>
  </select>

    <label for="pinInput">PIN</label>
    <input type="password" id="pinInput" placeholder="Enter PIN">

    <button id="loginBtn">Encrypt & Login</button>

    <div id="loginResults" class="response-box" style="display:none;">
      <h4>Encrypted Value</h4>
      <textarea id="encryptedValue" rows="2" readonly></textarea>

      <h4>X-Hash</h4>
      <textarea id="xHash" rows="2" readonly></textarea>

      <h4>Used Numbers</h4>
      <pre id="usedNumbers"></pre>
    </div>
  </div>

  <!-- ---------- API Responses ---------- -->
  <div class="card" id="apiResponses" style="display:none;">
    <h3>2️⃣ API Responses</h3>
    <div id="allApiResponses"></div>
  </div>

</div>

<script>
  // Use relative paths so remote users call the server that served the page
  const apiBase = ""; // empty -> use relative paths like "/api/encrypt"

  let xHashGlobal = "";

  function setLoading(button, state) {
    if(state){
      button.disabled = true;
      button.textContent = "Processing...";
    } else {
      button.disabled = false;
      button.textContent = button.getAttribute("data-original") || "Submit";
    }
  }

  // Login & API calls
  const loginBtn = document.getElementById("loginBtn");
  loginBtn.setAttribute("data-original", loginBtn.textContent);
  loginBtn.addEventListener("click", async () => {
    const number = document.getElementById("numberInput").value;
    const pin = document.getElementById("pinInput").value;
    if (!pin) { alert("Enter PIN"); return; }

    setLoading(loginBtn, true);

    try {
      const res = await fetch(`/api/encrypt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ number, pin })
      });
      const data = await res.json();
      if(data.error) { throw new Error(data.error); }

      document.getElementById("encryptedValue").value = data.encryptedValue || "";
      document.getElementById("xHash").value = data.xHash || "";
      xHashGlobal = data.xHash || "";

      // show used numbers
      document.getElementById("usedNumbers").textContent = JSON.stringify({
        usedNumber: data.usedNumber,
        pureNumber: data.pureNumber
      }, null, 2);

      document.getElementById("loginResults").style.display = "block";

      // Display all API responses
      const apiContainer = document.getElementById("allApiResponses");
      apiContainer.innerHTML = "";
      const additionalApis = data.additionalApis || {};
      Object.keys(additionalApis).forEach(key => {
        const div = document.createElement("div");
        div.className = "response-box";
        div.innerHTML = `<h4>${key}</h4><pre>${JSON.stringify(additionalApis[key], null, 2)}</pre>`;
        apiContainer.appendChild(div);
      });
      document.getElementById("apiResponses").style.display = "block";

    } catch (err) {
      console.error("Login/API error:", err);
      alert("Login/API error: " + (err.message || JSON.stringify(err)));
    } finally {
      setLoading(loginBtn, false);
    }
  });
</script>
</body>
</html>
"""
    resp = make_response(html)
    resp.headers["Content-Type"] = "text/html"
    return resp


# ---- Run ----
if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "True").lower() in ("1", "true", "yes")
    # updated port per your request
    app.run(port=int(os.environ.get("PORT", 5020)), host="0.0.0.0", debug=debug_mode)
