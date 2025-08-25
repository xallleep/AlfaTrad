from flask import Flask, render_template, jsonify
import requests
import numpy as np
from datetime import datetime, timedelta
import time
import threading
import os

app = Flask(__name__)

# Estado global do sistema
market_data = {
    'status': 'active',
    'current_price': 50000,  # Valor inicial até a primeira atualização
    'price_change': 0,
    'price_change_percent': 0,
    'direction': '↔️ ESTÁVEL',
    'confidence': 50,
    'trend_strength': 'NEUTRA',
    'last_update': datetime.now().strftime('%H:%M:%S'),
    'prediction_time': (datetime.now() + timedelta(minutes=90)).strftime('%H:%M'),
    'analysis': {
        'trend_score': 0,
        'rsi_score': 0,
        'macd_score': 0,
        'bb_score': 0,
        'total_score': 0,
        'rsi_value': 50.0,
        'macd_value': 0.0,
        'bb_position': 0.5
    },
    'indicators': {
        'sma_20': 50000,
        'sma_50': 50000,
        'ema_12': 50000,
        'ema_26': 50000,
        'rsi': 50.0,
        'macd': 0.0,
        'bb_upper': 51000,
        'bb_lower': 49000
    },
    'update_count': 0
}

# Histórico de preços para cálculo de indicadores
price_history = []

def get_bitcoin_price():
    """Obtém o preço real do Bitcoin de forma confiável"""
    try:
        # Tentativa com CoinGecko
        response = requests.get(
            'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true',
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'bitcoin' in data:
                return data['bitcoin']['usd'], data['bitcoin']['usd_24h_change'], True
        
        # Fallback para Binance
        response = requests.get(
            'https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT',
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            current_price = float(data['lastPrice'])
            price_change_percent = float(data['priceChangePercent'])
            return current_price, price_change_percent, True
            
    except Exception as e:
        print(f"Erro ao obter preço: {e}")
    
    # Fallback final - retorna o último preço conhecido
    return market_data['current_price'], market_data['price_change_percent'], False

def calculate_indicators(current_price):
    """Calcula indicadores técnicos baseados no histórico de preços"""
    global price_history
    
    # Adicionar preço atual ao histórico
    price_history.append(current_price)
    
    # Manter apenas os últimos 100 preços
    if len(price_history) > 100:
        price_history = price_history[-100:]
    
    # Calcular médias móveis se tivermos dados suficientes
    if len(price_history) >= 20:
        sma_20 = sum(price_history[-20:]) / 20
    else:
        sma_20 = sum(price_history) / len(price_history)
    
    if len(price_history) >= 50:
        sma_50 = sum(price_history[-50:]) / 50
    else:
        sma_50 = sum(price_history) / len(price_history)
    
    # Calcular EMA (simplificado)
    ema_12 = current_price if not price_history else (current_price * 0.15) + (price_history[-1] * 0.85)
    ema_26 = current_price if not price_history else (current_price * 0.07) + (price_history[-1] * 0.93)
    
    # Calcular RSI (simplificado)
    gains = []
    losses = []
    for i in range(1, min(14, len(price_history))):
        change = price_history[i] - price_history[i-1]
        if change > 0:
            gains.append(change)
        else:
            losses.append(abs(change))
    
    avg_gain = sum(gains) / len(gains) if gains else 0
    avg_loss = sum(losses) / len(losses) if losses else 0
    
    if avg_loss == 0:
        rsi = 100
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
    
    # Calcular MACD (simplificado)
    macd = ema_12 - ema_26
    
    # Calcular Bandas de Bollinger
    if len(price_history) >= 20:
        recent_prices = price_history[-20:]
        middle_band = sum(recent_prices) / 20
        std_dev = np.std(recent_prices)
        upper_band = middle_band + (std_dev * 2)
        lower_band = middle_band - (std_dev * 2)
        bb_position = (current_price - lower_band) / (upper_band - lower_band) if (upper_band - lower_band) > 0 else 0.5
    else:
        middle_band = current_price
        std_dev = current_price * 0.02
        upper_band = current_price + (std_dev * 2)
        lower_band = current_price - (std_dev * 2)
        bb_position = 0.5
    
    return {
        'sma_20': sma_20,
        'sma_50': sma_50,
        'ema_12': ema_12,
        'ema_26': ema_26,
        'rsi': rsi,
        'macd': macd,
        'bb_upper': upper_band,
        'bb_lower': lower_band,
        'bb_middle': middle_band,
        'bb_position': bb_position
    }

def calculate_analysis(current_price, price_change_percent, indicators):
    """Realiza análise baseada nos indicadores"""
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
        confidence = 50
        strength = 'NEUTRA'
    
    # Ajustar confiança baseada nos indicadores
    if indicators['rsi'] < 30 or indicators['rsi'] > 70:
        confidence += 5
    if abs(indicators['macd']) > current_price * 0.001:
        confidence += 5
    
    # Garantir que a confiança está entre 0 e 100
    confidence = max(0, min(100, confidence))
    
    # Calcular scores
    trend_score = 2 if price_change_percent > 0.1 else 1 if price_change_percent > 0 else -1 if price_change_percent < -0.1 else 0
    rsi_score = 1 if indicators['rsi'] < 40 else -1 if indicators['rsi'] > 60 else 0
    macd_score = 1 if indicators['macd'] > 0 else -1
    bb_score = 1 if current_price < indicators['bb_lower'] * 1.02 else -1 if current_price > indicators['bb_upper'] * 0.98 else 0
    
    total_score = trend_score + rsi_score + macd_score + bb_score
    
    return {
        'direction': direction,
        'confidence': round(confidence),
        'trend_strength': strength,
        'analysis': {
            'trend_score': trend_score,
            'rsi_score': rsi_score,
            'macd_score': macd_score,
            'bb_score': bb_score,
            'total_score': total_score,
            'rsi_value': round(indicators['rsi'], 2),
            'macd_value': round(indicators['macd'], 2),
            'bb_position': round(indicators['bb_position'], 2)
        }
    }

def update_market_data():
    """Atualiza os dados do mercado de forma eficiente"""
    global market_data, price_history
    
    while True:
        try:
            # Obter preço atual
            current_price, price_change_percent, success = get_bitcoin_price()
            
            if success:
                # Calcular indicadores
                indicators = calculate_indicators(current_price)
                
                # Fazer análise
                analysis_result = calculate_analysis(current_price, price_change_percent, indicators)
                
                # Calcular variação de preço
                previous_price = market_data['current_price']
                price_change = current_price - previous_price
                
                # Atualizar dados
                market_data.update({
                    'current_price': current_price,
                    'price_change': price_change,
                    'price_change_percent': price_change_percent,
                    'direction': analysis_result['direction'],
                    'confidence': analysis_result['confidence'],
                    'trend_strength': analysis_result['trend_strength'],
                    'indicators': {k: v for k, v in indicators.items() if k != 'bb_middle' and k != 'bb_position'},
                    'analysis': analysis_result['analysis'],
                    'last_update': datetime.now().strftime('%H:%M:%S'),
                    'prediction_time': (datetime.now() + timedelta(minutes=90)).strftime('%H:%M'),
                    'update_count': market_data['update_count'] + 1
                })
                
                print(f"✅ {analysis_result['direction']} | ${current_price:.2f} | Conf: {analysis_result['confidence']}%")
            else:
                print("⚠️  Usando dados anteriores (falha na API)")
            
            time.sleep(30)  # Atualizar a cada 30 segundos (evitar rate limiting)
            
        except Exception as e:
            print(f"❌ Erro na atualização: {e}")
            time.sleep(60)  # Esperar mais em caso de erro

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
        'timestamp': datetime.now().isoformat(),
        'update_count': market_data['update_count']
    })

# Iniciar thread de atualização
update_thread = threading.Thread(target=update_market_data, daemon=True)
update_thread.start()

if __name__ == '__main__':
    print("🚀 Bitcoin Predictor Pro Iniciado!")
    print("💡 Iniciando coleta de dados...")
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)