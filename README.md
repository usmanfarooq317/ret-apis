# 🔐 IBM/RSA RET-API Dashboard (Flask + Docker)

This project provides a single-file Flask application with an embedded HTML dashboard to:
✔ Encrypt login credentials using RSA  
✔ Authenticate using IBM CorporateLogin API  
✔ Automatically call other APIs after successful login  
✔ Display all responses in a clean dashboard  
✔ Fully containerized using Docker & docker-compose  

---

## 🚀 Features

- Python + Flask backend (single file `app.py`)
- HTML/CSS/JS frontend embedded inside Python
- Uses RSA encryption (IBM public key)
- No timeout for API requests (as requested)
- Uses port `5020`
- Docker & docker-compose supported
- Jenkins Added
- Simple `requirements.txt` file

---

## 📁 Project Structure

.
├── app.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── README.md
└── retailergateway.pem # IBM Public Key (must be placed manually)


---

## ⚙️ Environment Variables (Optional)

You can set these in your system or inside `docker-compose.yml` if you want:

| Variable Name        | Description                        | Default Value |
|----------------------|------------------------------------|---------------|
| IBM_CLIENT_ID        | IBM API Client ID                  | 924726...     |
| IBM_CLIENT_SECRET    | IBM API Client Secret              | 7154c9...     |
| X_CHANNEL            | API Channel Header                 | retailergateway |

---

## 🖥️ Run Locally (Without Docker)

```bash
pip install -r requirements.txt
python app.py
Then open in browser:


http://127.0.0.1:5020
🐳 Run with Docker
1. Build Docker Image
bash

docker build -t ibm-rsa-dashboard .
2. Run the Container
bash

docker run -p 5020:5020 ibm-rsa-dashboard
🐙 Run with docker-compose
bash

docker-compose up --build
✅ Requirements
Python 3.8+

Flask, Requests, Cryptography library

Docker & docker-compose (optional but recommended)

📌 Notes
Make sure to place the retailergateway.pem public key in the same folder as app.py

No request timeout has been added (as requested)

Port is fixed to 5020

