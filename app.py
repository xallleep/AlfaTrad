from flask import Flask, render_template, jsonify
import numpy as np
from datetime import datetime, timedelta
import requests
import time
import json

app = Flask(__name__)

# Configurações
UPDATE_INTERVAL = 60  # Atualizar a cada 60 segundos

# Cache para dados
cache = {
    'current_price': 0,
    'prediction': 0,
    'confidence': 0,
    'trend': 'NEUTRO',
    'last_update': None,
    'history': []
}

# Buscar preço atual do Bitcoin
def get_btc_price():
    try:
        response = requests.get(
            'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true',
            timeout=10
        )
        data = response.json()
        return data['bitcoin']['usd'], data['bitcoin']['usd_24h_change']
    except:
        # Fallback em caso de erro
        return 40000, 0

# Algoritmo de previsão eficiente para 1.5 hora
def predict_90_minutes(history):
    if len(history) < 10:
        return 0, 0, "Dados insuficientes"
    
    try:
        # Últimos preços
        recent_prices = [h['price'] for h in history[-10:]]
        
        # Calcular tendência recente (últimos 30 minutos)
        short_term_trend = np.polyfit(range(len(recent_prices)), recent_prices, 1)[0]
        
        # Calcular volatilidade
        changes = np.diff(recent_prices) / recent_prices[:-1]
        volatility = np.std(changes) if len(changes) > 0 else 0.001
        
        # Calcular momentum
        momentum = sum(changes[-3:]) / 3 if len(changes) >= 3 else 0
        
        # Fatores de influência (simulados)
        market_sentiment = np.random.normal(0, 0.0005)  # Pequena influência aleatória
        
        # Previsão principal
        current_price = recent_prices[-1]
        predicted_change = (short_term_trend * 90/5) + (momentum * 2) + market_sentiment
        
        # Ajustar pela volatilidade
        volatility_factor = 1 + (volatility * 10)
        predicted_price = current_price * (1 + predicted_change * volatility_factor)
        
        # Calcular confiança (0-100%)
        confidence = max(0, min(100, 70 - (volatility * 1000)))
        
        # Determinar tendência
        if predicted_change > 0.001:
            trend = "ALTA 📈"
        elif predicted_change < -0.001:
            trend = "BAIXA 📉"
        else:
            trend = "NEUTRO ⏸️"
        
        return round(predicted_price, 2), round(confidence, 1), trend
        
    except Exception as e:
        print(f"Erro na previsão: {e}")
        return 0, 0, "Erro"

# Atualizar dados
def update_data():
    try:
        current_price, daily_change = get_btc_price()
        
        # Adicionar ao histórico
        cache['history'].append({
            'timestamp': datetime.now(),
            'price': current_price,
            'daily_change': daily_change
        })
        
        # Manter apenas últimas 100 entradas
        if len(cache['history']) > 100:
            cache['history'] = cache['history'][-100:]
        
        # Fazer previsão
        predicted_price, confidence, trend = predict_90_minutes(cache['history'])
        
        # Atualizar cache
        cache['current_price'] = current_price
        cache['prediction'] = predicted_price
        cache['confidence'] = confidence
        cache['trend'] = trend
        cache['last_update'] = datetime.now()
        
        print(f"Atualizado: ${current_price} → Previsão: ${predicted_price} ({confidence}%)")
        
    except Exception as e:
        print(f"Erro na atualização: {e}")

# Rotas
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/data')
def get_data():
    return jsonify({
        'current_price': cache['current_price'],
        'prediction': cache['prediction'],
        'confidence': cache['confidence'],
        'trend': cache['trend'],
        'last_update': cache['last_update'].strftime('%H:%M:%S') if cache['last_update'] else 'N/A',
        'next_update': (cache['last_update'] + timedelta(seconds=UPDATE_INTERVAL)).strftime('%H:%M:%S') if cache['last_update'] else 'N/A',
        'history_count': len(cache['history'])
    })

@app.route('/api/update')
def manual_update():
    update_data()
    return jsonify({'status': 'success', 'message': 'Dados atualizados manualmente'})

# Inicializar e agendar atualizações
def start_scheduler():
    import threading
    def scheduler():
        while True:
            update_data()
            time.sleep(UPDATE_INTERVAL)
    
    # Iniciar thread em background
    thread = threading.Thread(target=scheduler, daemon=True)
    thread.start()

# Iniciar scheduler quando o app iniciar
with app.app_context():
    update_data()  # Primeira atualização
    start_scheduler()  # Iniciar atualizações automáticas

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)