# ZTP NOC Dashboard (Fresh Build)

Modern dashboard UI for a Zero-Touch Network Provisioning system with:
- Dark NOC-style interface
- Modular component-based frontend (`api.js`, `components.js`, `main.js`)
- Real-time status refresh every 1.5 seconds
- Flask backend endpoints: `/status`, `/run`, `/scan`, `/stop`

## Run

```bash
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5000`.
