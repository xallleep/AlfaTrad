from flask import Flask, render_template, jsonify
import requests
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import time
import threading
import talib
from scipy import stats

app = Flask(__name__)

# Estado global do sistema
market_data = {
    'status': 'active',
    'current_price': 0,
    'price_change': 0,
    'price_change_percent': 0,
    'direction': '🔄 ANALISANDO',
    'confidence': 50,
    'trend_strength': 'COLETANDO DADOS',
    'last_update': datetime.now().strftime('%H:%M:%S'),
    'prediction_time': (datetime.now() + timedelta(minutes=90)).strftime('%H:%M'),
    'history': [],
    'analysis': {},
    'indicators': {},
    'update_count': 0
}

def get_bitcoin_data():
    """Obtém dados completos do Bitcoin"""
    try:
        # API do CoinGecko para dados mais completos
        response = requests.get(
            'https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=1&interval=5m',
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            prices = data['prices']
            
            # Pegar o preço mais recente
            current_price = prices[-1][1]
            previous_price = prices[-2][1] if len(prices) > 1 else current_price
            
            # Calcular variação
            price_change = current_price - previous_price
            price_change_percent = (price_change / previous_price) * 100
            
            return current_price, price_change, price_change_percent, True
            
    except Exception as e:
        print(f"Erro ao buscar dados: {e}")
    
    return market_data['current_price'], 0, 0, False

def calculate_technical_indicators(prices):
    """Calcula todos os indicadores técnicos"""
    if len(prices) < 20:
        return {}
    
    prices_array = np.array(prices)
    
    # Médias Móveis
    sma_20 = talib.SMA(prices_array, timeperiod=20)
    sma_50 = talib.SMA(prices_array, timeperiod=50)
    ema_12 = talib.EMA(prices_array, timeperiod=12)
    ema_26 = talib.EMA(prices_array, timeperiod=26)
    
    # RSI
    rsi = talib.RSI(prices_array, timeperiod=14)
    
    # MACD
    macd, macd_signal, macd_hist = talib.MACD(prices_array)
    
    # Bollinger Bands
    bb_upper, bb_middle, bb_lower = talib.BBANDS(prices_array)
    
    # Estocástico (simulado)
    stoch_k = talib.STOCH(prices_array, prices_array, prices_array)[0]
    stoch_d = talib.STOCH(prices_array, prices_array, prices_array)[1]
    
    return {
        'sma_20': sma_20[-1] if not np.isnan(sma_20[-1]) else prices[-1],
        'sma_50': sma_50[-1] if not np.isnan(sma_50[-1]) else prices[-1],
        'ema_12': ema_12[-1] if not np.isnan(ema_12[-1]) else prices[-1],
        'ema_26': ema_26[-1] if not np.isnan(ema_26[-1]) else prices[-1],
        'rsi': rsi[-1] if not np.isnan(rsi[-1]) else 50,
        'macd': macd[-1] if not np.isnan(macd[-1]) else 0,
        'macd_signal': macd_signal[-1] if not np.isnan(macd_signal[-1]) else 0,
        'bb_upper': bb_upper[-1] if not np.isnan(bb_upper[-1]) else prices[-1],
        'bb_lower': bb_lower[-1] if not np.isnan(bb_lower[-1]) else prices[-1],
        'stoch_k': stoch_k[-1] if not np.isnan(stoch_k[-1]) else 50,
        'stoch_d': stoch_d[-1] if not np.isnan(stoch_d[-1]) else 50
    }

def analyze_market_with_multiple_methods(prices, indicators):
    """Analisa o mercado usando múltiplos métodos"""
    if len(prices) < 20:
        return '🔄 ANALISANDO', 50, 'DADOS INSUFICIENTES', {}
    
    current_price = prices[-1]
    analysis_results = {}
    
    # 1. Análise de Tendência (Médias Móveis)
    trend_score = 0
    if indicators['sma_20'] > indicators['sma_50']:
        trend_score += 1
    if indicators['ema_12'] > indicators['ema_26']:
        trend_score += 1
    if current_price > indicators['sma_20']:
        trend_score += 1
    
    # 2. Análise RSI
    rsi_score = 0
    if indicators['rsi'] < 30:
        rsi_score = 1  # Sobrevendido - potencial compra
    elif indicators['rsi'] > 70:
        rsi_score = -1  # Sobrecomprado - potencial venda
    
    # 3. Análise MACD
    macd_score = 1 if indicators['macd'] > indicators['macd_signal'] else -1
    
    # 4. Análise Bollinger Bands
    bb_score = 0
    bb_position = (current_price - indicators['bb_lower']) / (indicators['bb_upper'] - indicators['bb_lower'])
    if bb_position < 0.2:
        bb_score = 1  # Perto da banda inferior - potencial compra
    elif bb_position > 0.8:
        bb_score = -1  # Perto da banda superior - potencial venda
    
    # 5. Análise Estocástico
    stoch_score = 1 if indicators['stoch_k'] < 20 else -1 if indicators['stoch_k'] > 80 else 0
    
    # Pontuação total
    total_score = trend_score + rsi_score + macd_score + bb_score + stoch_score
    
    # Determinar direção
    if total_score >= 3:
        direction = '📈 SUBINDO'
        confidence = min(95, 60 + total_score * 5)
        strength = 'FORTE'
    elif total_score >= 1:
        direction = '📈 SUBINDO'
        confidence = min(85, 55 + total_score * 5)
        strength = 'MODERADA'
    elif total_score <= -3:
        direction = '📉 DESCENDO'
        confidence = min(95, 60 + abs(total_score) * 5)
        strength = 'FORTE'
    elif total_score <= -1:
        direction = '📉 DESCENDO'
        confidence = min(85, 55 + abs(total_score) * 5)
        strength = 'MODERADA'
    else:
        direction = '↔️ ESTÁVEL'
        confidence = 75
        strength = 'NEUTRA'
    
    analysis_results = {
        'trend_score': trend_score,
        'rsi_score': rsi_score,
        'macd_score': macd_score,
        'bb_score': bb_score,
        'stoch_score': stoch_score,
        'total_score': total_score,
        'rsi_value': indicators['rsi'],
        'macd_value': indicators['macd'],
        'bb_position': bb_position
    }
    
    return direction, confidence, strength, analysis_results

def update_market_data():
    """Atualiza os dados do mercado"""
    while True:
        try:
            # Obter dados atualizados
            current_price, price_change, price_change_percent, success = get_bitcoin_data()
            
            if success:
                market_data['current_price'] = current_price
                market_data['price_change'] = price_change
                market_data['price_change_percent'] = price_change_percent
                market_data['history'].append(current_price)
                
                # Manter histórico gerenciável
                if len(market_data['history']) > 100:
                    market_data['history'] = market_data['history'][-100:]
                
                # Calcular indicadores técnicos
                indicators = calculate_technical_indicators(market_data['history'])
                market_data['indicators'] = indicators
                
                # Fazer análise completa
                direction, confidence, strength, analysis = analyze_market_with_multiple_methods(
                    market_data['history'], indicators
                )
                
                # Atualizar dados
                market_data['direction'] = direction
                market_data['confidence'] = confidence
                market_data['trend_strength'] = strength
                market_data['analysis'] = analysis
                market_data['last_update'] = datetime.now().strftime('%H:%M:%S')
                market_data['prediction_time'] = (datetime.now() + timedelta(minutes=90)).strftime('%H:%M')
                market_data['update_count'] += 1
                
                print(f"✅ {direction} | Conf: {confidence}% | Força: {strength}")
            
            time.sleep(30)  # Atualizar a cada 30 segundos
            
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
        'update_count': market_data['update_count'],
        'history_size': len(market_data['history'])
    })

# Iniciar thread de atualização
update_thread = threading.Thread(target=update_market_data, daemon=True)
update_thread.start()

if __name__ == '__main__':
    # Inicializar com dados
    market_data['current_price'], _, _, _ = get_bitcoin_data()
    market_data['history'] = [market_data['current_price']] * 50
    
    print("🚀 Bitcoin Predictor Pro Iniciado!")
    app.run(debug=False, host='0.0.0.0', port=5000)