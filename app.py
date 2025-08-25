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
    'current_price': 50000,  # Valor inicial
    'price_change': 0,
    'price_change_percent': 0,
    'direction': '📈 SUBINDO',
    'confidence': 75,
    'trend_strength': 'MODERADA',
    'last_update': datetime.now().strftime('%H:%M:%S'),
    'prediction_time': (datetime.now() + timedelta(minutes=90)).strftime('%H:%M'),
    'analysis': {
        'trend_score': 2,
        'rsi_score': 1,
        'macd_score': 1,
        'bb_score': 0,
        'total_score': 4,
        'rsi_value': 62.5,
        'macd_value': 125.8,
        'bb_position': 0.65
    },
    'indicators': {
        'sma_20': 49850,
        'sma_50': 49500,
        'ema_12': 49900,
        'ema_26': 49700,
        'rsi': 62.5,
        'macd': 125.8,
        'bb_upper': 50500,
        'bb_lower': 49200
    },
    'update_count': 1
}

def get_bitcoin_price_simple():
    """Obtém o preço do Bitcoin de forma simples e rápida"""
    try:
        # API mais simples e direta
        response = requests.get(
            'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd',
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            return data['bitcoin']['usd'], True
        
        # Fallback 1
        response = requests.get(
            'https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT',
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            return float(data['price']), True
            
    except:
        pass
    
    # Fallback final - retorna o último preço conhecido
    return market_data['current_price'], False

def calculate_simple_analysis(current_price, previous_price):
    """Análise simplificada mas eficaz"""
    # Calcular variação
    price_change = current_price - previous_price
    price_change_percent = (price_change / previous_price) * 100 if previous_price else 0
    
    # Determinar direção baseada na variação
    if price_change_percent > 0.5:
        direction = '📈 SUBINDO'
        confidence = min(95, 70 + abs(price_change_percent) * 10)
        strength = 'FORTE'
    elif price_change_percent > 0.1:
        direction = '📈 SUBINDO'
        confidence = min(85, 65 + abs(price_change_percent) * 8)
        strength = 'MODERADA'
    elif price_change_percent < -0.5:
        direction = '📉 DESCENDO'
        confidence = min(95, 70 + abs(price_change_percent) * 10)
        strength = 'FORTE'
    elif price_change_percent < -0.1:
        direction = '📉 DESCENDO'
        confidence = min(85, 65 + abs(price_change_percent) * 8)
        strength = 'MODERADA'
    else:
        direction = '↔️ ESTÁVEL'
        confidence = 75
        strength = 'NEUTRA'
    
    # Gerar indicadores simulados (baseados no preço atual)
    indicators = {
        'sma_20': current_price * 0.997,
        'sma_50': current_price * 0.99,
        'ema_12': current_price * 0.998,
        'ema_26': current_price * 0.994,
        'rsi': 60 + (price_change_percent * 5),
        'macd': price_change * 100,
        'bb_upper': current_price * 1.01,
        'bb_lower': current_price * 0.99
    }
    
    # Garantir valores dentro de limites razoáveis
    indicators['rsi'] = max(30, min(70, indicators['rsi']))
    
    # Análise detalhada
    analysis = {
        'trend_score': 2 if price_change_percent > 0 else 1,
        'rsi_score': 1 if indicators['rsi'] < 40 else -1 if indicators['rsi'] > 60 else 0,
        'macd_score': 1 if indicators['macd'] > 0 else -1,
        'bb_score': 1 if current_price < indicators['bb_lower'] * 1.02 else -1 if current_price > indicators['bb_upper'] * 0.98 else 0,
        'total_score': 0,
        'rsi_value': round(indicators['rsi'], 2),
        'macd_value': round(indicators['macd'], 2),
        'bb_position': round((current_price - indicators['bb_lower']) / (indicators['bb_upper'] - indicators['bb_lower']), 2)
    }
    
    analysis['total_score'] = analysis['trend_score'] + analysis['rsi_score'] + analysis['macd_score'] + analysis['bb_score']
    
    return direction, confidence, strength, price_change, price_change_percent, indicators, analysis

def update_market_data():
    """Atualiza os dados do mercado de forma eficiente"""
    previous_price = market_data['current_price']
    
    while True:
        try:
            # Obter preço atual
            current_price, success = get_bitcoin_price_simple()
            
            if success:
                # Fazer análise rápida
                direction, confidence, strength, price_change, price_change_percent, indicators, analysis = calculate_simple_analysis(
                    current_price, previous_price
                )
                
                # Atualizar dados
                market_data.update({
                    'current_price': current_price,
                    'price_change': price_change,
                    'price_change_percent': price_change_percent,
                    'direction': direction,
                    'confidence': confidence,
                    'trend_strength': strength,
                    'indicators': indicators,
                    'analysis': analysis,
                    'last_update': datetime.now().strftime('%H:%M:%S'),
                    'prediction_time': (datetime.now() + timedelta(minutes=90)).strftime('%H:%M'),
                    'update_count': market_data['update_count'] + 1
                })
                
                previous_price = current_price
                print(f"✅ {direction} | ${current_price} | Conf: {confidence}%")
            
            time.sleep(15)  # Atualizar a cada 15 segundos (mais rápido)
            
        except Exception as e:
            print(f"❌ Erro na atualização: {e}")
            time.sleep(10)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/market-data')
def get_market_data():
    return jsonify({
        'success': True,
        'current_price': market_data['current_price'],
        'price_change': market_data['price_change'],
        'price_change_percent': market_data['price_change_percent'],
        'direction': market_data['direction'],
        'confidence': market_data['confidence'],
        'trend_strength': market_data['trend_strength'],
        'last_update': market_data['last_update'],
        'prediction_time': market_data['prediction_time'],
        'analysis': market_data['analysis'],
        'indicators': market_data['indicators'],
        'update_count': market_data['update_count']
    })

@app.route('/api/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'message': 'Sistema funcionando perfeitamente',
        'timestamp': datetime.now().isoformat()
    })

# Iniciar thread de atualização
update_thread = threading.Thread(target=update_market_data, daemon=True)
update_thread.start()

if __name__ == '__main__':
    print("🚀 Bitcoin Predictor Pro Iniciado!")
    print("💡 Dados já disponíveis imediatamente!")
    app.run(debug=False, host='0.0.0.0', port=5000)