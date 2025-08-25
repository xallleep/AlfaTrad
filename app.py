from flask import Flask, render_template, jsonify
import requests
from datetime import datetime, timedelta
import time
import threading
import numpy as np

app = Flask(__name__)

# Configurações
UPDATE_INTERVAL = 30  # Atualizar a cada 30 segundos

# Cache para dados
cache = {
    'current_price': 0,
    'prediction': 0,
    'direction': 'NEUTRAL',
    'confidence': 50,
    'last_update': None,
    'price_history': [],
    'timestamp': None
}

# Buscar preço real do Bitcoin
def get_real_btc_price():
    try:
        # Tentar CoinGecko primeiro
        response = requests.get(
            'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true',
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            return data['bitcoin']['usd'], True
        
        # Fallback para API alternativa
        response = requests.get(
            'https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT',
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            return float(data['price']), True
            
    except:
        pass
    
    # Fallback final - manter último preço conhecido
    return cache['current_price'] if cache['current_price'] > 0 else 40000, False

# Algoritmo de previsão confiável
def predict_future_price():
    if len(cache['price_history']) < 5:
        return 0, 'NEUTRAL', 50
    
    try:
        # Usar os últimos 10 preços para análise
        recent_prices = cache['price_history'][-10:]
        
        # Calcular tendência simples
        prices_array = np.array(recent_prices)
        time_array = np.arange(len(prices_array))
        
        # Regressão linear para tendência
        slope, intercept = np.polyfit(time_array, prices_array, 1)
        
        # Prever para 90 minutos (18 intervalos de 5 minutos)
        future_price = slope * 18 + intercept
        
        # Calcular confiança baseada na consistência da tendência
        current_price = cache['current_price']
        price_change = ((future_price - current_price) / current_price) * 100
        
        # Determinar direção com confiança
        if abs(price_change) < 0.1:  # Menos de 0.1% de mudança
            return future_price, 'NEUTRAL', 60
        
        elif price_change > 0:
            confidence = min(90, 60 + abs(price_change) * 2)
            return future_price, 'UP', confidence
        
        else:
            confidence = min(90, 60 + abs(price_change) * 2)
            return future_price, 'DOWN', confidence
            
    except Exception as e:
        print(f"Erro na previsão: {e}")
        return cache['current_price'], 'NEUTRAL', 50

# Atualizar dados
def update_btc_data():
    while True:
        try:
            current_price, success = get_real_btc_price()
            
            if success:
                cache['current_price'] = current_price
                cache['price_history'].append(current_price)
                
                # Manter apenas histórico recente
                if len(cache['price_history']) > 50:
                    cache['price_history'] = cache['price_history'][-50:]
                
                # Fazer previsão
                future_price, direction, confidence = predict_future_price()
                
                cache['prediction'] = round(future_price, 2)
                cache['direction'] = direction
                cache['confidence'] = min(95, confidence)  # Limitar a 95% para ser conservador
                cache['last_update'] = datetime.now().strftime('%H:%M:%S')
                cache['timestamp'] = datetime.now().isoformat()
                
                print(f"✅ Preço: ${current_price} | Previsão: {direction} | Confiança: {confidence}%")
                
            else:
                print("⚠️  Usando dados em cache")
                
        except Exception as e:
            print(f"❌ Erro na atualização: {e}")
        
        time.sleep(UPDATE_INTERVAL)

# Rotas
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    return jsonify({
        'current_price': cache['current_price'],
        'prediction': cache['prediction'],
        'direction': cache['direction'],
        'confidence': cache['confidence'],
        'last_update': cache['last_update'],
        'timestamp': cache['timestamp'],
        'history_count': len(cache['price_history']),
        'status': 'success'
    })

@app.route('/api/health')
def health_check():
    return jsonify({'status': 'healthy', 'updated': cache['last_update'] is not None})

# Iniciar thread de atualização em background
def start_update_thread():
    thread = threading.Thread(target=update_btc_data, daemon=True)
    thread.start()
    print("🔄 Thread de atualização iniciada")

# Inicialização
with app.app_context():
    # Primeira atualização imediata
    current_price, success = get_real_btc_price()
    cache['current_price'] = current_price
    cache['price_history'] = [current_price]
    cache['last_update'] = datetime.now().strftime('%H:%M:%S')
    cache['timestamp'] = datetime.now().isoformat()
    
    # Iniciar thread de atualização
    start_update_thread()

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)