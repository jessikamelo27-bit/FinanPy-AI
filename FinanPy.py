""" Ponto de entrada alternativo que executa o servidor FinanPy AI PRO (app.py). """

from app import app

if __name__ == "__main__":
    print("[FinanPy AI PRO] Servidor Dark Fintech iniciado em http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)
