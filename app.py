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
    'current_price': None,
    'direction': 'ANALISANDO',
    'confidence': 0,
    'prediction_time': None,
    'trend_strength': 'MODERADA',
    'last_update': None,
    'price_history': []
}

# Buscar preço real do Bitcoin
def get_real_btc_price():
    try:
        # Múltiplas fontes para confiabilidade
        apis = [
            'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd',
            'https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT',
            'https://api.coinbase.com/v2/prices/BTC-USD/spot'
        ]
        
        for api_url in apis:
            try:
                response = requests.get(api_url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if 'bitcoin' in api_url:
                        return data['bitcoin']['usd'], True
                    elif 'binance' in api_url:
                        return float(data['price']), True
                    elif 'coinbase' in api_url:
                        return float(data['data']['amount']), True
            except:
                continue
                
        return None, False
        
    except Exception as e:
        print(f"Erro ao buscar preço: {e}")
        return None, False

# Análise técnica realista
def analyze_trend():
    if len(cache['price_history']) < 10:
        return 'ANALISANDO', 0, 'COLETANDO DADOS'
    
    try:
        prices = np.array(cache['price_history'][-30:])  # Últimos 30 preços
        
        # Análise de tendência de curto prazo (últimos 15 minutos)
        short_term = prices[-6:]  # 6 preços = 3 minutos
        short_slope = np.polyfit(range(len(short_term)), short_term, 1)[0]
        
        # Análise de tendência de médio prazo (última hora)
        medium_term = prices[-30:]  # 30 preços = 15 minutos
        medium_slope = np.polyfit(range(len(medium_term)), medium_term, 1)[0]
        
        # Calcular força da tendência
        trend_strength = abs(medium_slope) * 10000  # Normalizar
        
        # Determinar direção baseada nas duas análises
        if short_slope > 0 and medium_slope > 0:
            direction = 'SUBINDO ↗️'
            confidence = min(95, 70 + int(trend_strength * 10))
        elif short_slope < 0 and medium_slope < 0:
            direction = 'DESCENDO ↘️'
            confidence = min(95, 70 + int(trend_strength * 10))
        elif abs(short_slope) < 0.1 and abs(medium_slope) < 0.1:
            direction = 'ESTÁVEL →'
            confidence = 75
        else:
            # Tendências conflitantes
            direction = 'INDECISO 🔄'
            confidence = 50
        
        # Determinar força da tendência
        if trend_strength > 2:
            strength = 'FORTE'
        elif trend_strength > 0.5:
            strength = 'MODERADA'
        else:
            strength = 'FRACA'
        
        return direction, confidence, strength
        
    except Exception as e:
        print(f"Erro na análise: {e}")
        return 'ANALISANDO', 0, 'EM ANÁLISE'

# Atualizar dados
def update_btc_data():
    while True:
        try:
            current_price, success = get_real_btc_price()
            
            if success and current_price is not None:
                cache['current_price'] = current_price
                cache['price_history'].append(current_price)
                
                # Manter histórico gerenciável
                if len(cache['price_history']) > 100:
                    cache['price_history'] = cache['price_history'][-100:]
                
                # Fazer análise
                direction, confidence, strength = analyze_trend()
                
                cache['direction'] = direction
                cache['confidence'] = confidence
                cache['trend_strength'] = strength
                cache['prediction_time'] = (datetime.now() + timedelta(minutes=90)).strftime('%H:%M')
                cache['last_update'] = datetime.now().strftime('%H:%M:%S')
                
                print(f"📊 {direction} | Confiança: {confidence}% | Força: {strength}")
                
            else:
                print("⚠️  Aguardando dados...")
                
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
        'direction': cache['direction'],
        'confidence': cache['confidence'],
        'trend_strength': cache['trend_strength'],
        'prediction_time': cache['prediction_time'],
        'last_update': cache['last_update'],
        'history_count': len(cache['price_history']),
        'status': 'success'
    })

@app.route('/api/health')
def health_check():
    return jsonify({
        'status': 'healthy', 
        'has_data': len(cache['price_history']) > 0,
        'updated': cache['last_update']
    })

# Iniciar thread de atualização
def start_update_thread():
    thread = threading.Thread(target=update_btc_data, daemon=True)
    thread.start()
    print("🔄 Sistema de análise iniciado")

# Inicialização
with app.app_context():
    start_update_thread()

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)