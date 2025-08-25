from flask import Flask, render_template, jsonify
import requests
import numpy as np
from datetime import datetime, timedelta
import time
import threading

app = Flask(__name__)

# Estado global do sistema
market_data = {
    'status': 'active',
    'bitcoin_price': 0,
    'direction': '🔄 ANALISANDO',
    'confidence': 50,
    'trend_strength': 'COLETANDO DADOS',
    'last_update': datetime.now().strftime('%H:%M:%S'),
    'prediction_time': (datetime.now() + timedelta(minutes=90)).strftime('%H:%M'),
    'history': [],
    'update_count': 0
}

def get_bitcoin_price():
    """Obtém o preço real do Bitcoin de múltiplas fontes"""
    try:
        # Tentar CoinGecko primeiro
        response = requests.get(
            'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd',
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            return data['bitcoin']['usd'], True

        # Fallback para Binance
        response = requests.get(
            'https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT',
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            return float(data['price']), True

    except Exception as e:
        print(f"Erro ao buscar preço: {e}")

    return market_data['bitcoin_price'], False

def analyze_market_trend():
    """Analisa a tendência do mercado com algoritmo realista"""
    if len(market_data['history']) < 10:
        return '🔄 ANALISANDO', 50, 'COLETANDO DADOS'

    try:
        prices = np.array(market_data['history'][-20:])  # Últimos 20 preços
        
        # Calcular tendência de curto prazo
        short_term = prices[-5:]
        short_trend = np.polyfit(range(len(short_term)), short_term, 1)[0]
        
        # Calcular tendência de médio prazo
        medium_trend = np.polyfit(range(len(prices)), prices, 1)[0]
        
        # Calcular volatilidade
        price_changes = np.diff(prices) / prices[:-1]
        volatility = np.std(price_changes) * 100 if len(price_changes) > 0 else 0.5
        
        # Determinar direção baseada nas tendências
        if short_trend > 0 and medium_trend > 0:
            direction = '📈 SUBINDO'
            confidence = min(95, 70 + int(volatility * 2))
            strength = 'FORTE' if volatility > 1 else 'MODERADA'
        elif short_trend < 0 and medium_trend < 0:
            direction = '📉 DESCENDO'
            confidence = min(95, 70 + int(volatility * 2))
            strength = 'FORTE' if volatility > 1 else 'MODERADA'
        else:
            direction = '↔️ ESTÁVEL'
            confidence = 75
            strength = 'NEUTRA'

        return direction, confidence, strength

    except Exception as e:
        print(f"Erro na análise: {e}")
        return '🔄 ANALISANDO', 50, 'EM ANÁLISE'

def update_market_data():
    """Atualiza os dados do mercado a cada 30 segundos"""
    while True:
        try:
            # Obter preço atual
            new_price, success = get_bitcoin_price()
            
            if success:
                market_data['bitcoin_price'] = new_price
                market_data['history'].append(new_price)
                
                # Manter histórico gerenciável
                if len(market_data['history']) > 50:
                    market_data['history'] = market_data['history'][-50:]
                
                # Analisar tendência
                direction, confidence, strength = analyze_market_trend()
                
                # Atualizar dados
                market_data['direction'] = direction
                market_data['confidence'] = confidence
                market_data['trend_strength'] = strength
                market_data['last_update'] = datetime.now().strftime('%H:%M:%S')
                market_data['prediction_time'] = (datetime.now() + timedelta(minutes=90)).strftime('%H:%M')
                market_data['update_count'] += 1
                
                print(f"✅ Atualizado: {direction} | Confiança: {confidence}%")

            time.sleep(30)  # Atualizar a cada 30 segundos
            
        except Exception as e:
            print(f"❌ Erro na atualização: {e}")
            time.sleep(10)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/data')
def get_data():
    return jsonify({
        'success': True,
        'direction': market_data['direction'],
        'confidence': market_data['confidence'],
        'trend_strength': market_data['trend_strength'],
        'last_update': market_data['last_update'],
        'prediction_time': market_data['prediction_time'],
        'update_count': market_data['update_count'],
        'history_size': len(market_data['history'])
    })

@app.route('/api/price')
def get_price():
    return jsonify({
        'price': market_data['bitcoin_price'],
        'currency': 'USD'
    })

# Iniciar thread de atualização em background
update_thread = threading.Thread(target=update_market_data, daemon=True)
update_thread.start()

if __name__ == '__main__':
    # Primeira atualização imediata
    initial_price, _ = get_bitcoin_price()
    market_data['bitcoin_price'] = initial_price
    market_data['history'] = [initial_price] * 10  # Inicializar com dados
    
    print("🚀 Bitcoin Predictor Pro Iniciado!")
    app.run(debug=False, host='0.0.0.0', port=5000)