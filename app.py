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
            prices = [p[1] for p in data['prices']]
            
            # Pegar o preço mais recente
            current_price = prices[-1]
            previous_price = prices[-2] if len(prices) > 1 else current_price
            
            # Calcular variação
            price_change = current_price - previous_price
            price_change_percent = (price_change / previous_price) * 100
            
            return current_price, price_change, price_change_percent, prices, True
            
    except Exception as e:
        print(f"Erro ao buscar dados: {e}")
    
    return market_data['current_price'], 0, 0, [], False

def calculate_sma(prices, period):
    """Calcula Simple Moving Average manualmente"""
    if len(prices) < period:
        return np.nan
    return np.mean(prices[-period:])

def calculate_ema(prices, period):
    """Calcula Exponential Moving Average manualmente"""
    if len(prices) < period:
        return np.nan
    
    weights = np.exp(np.linspace(-1., 0., period))
    weights /= weights.sum()
    
    return np.convolve(prices[-period:], weights, mode='valid')[-1]

def calculate_rsi(prices, period=14):
    """Calcula RSI manualmente"""
    if len(prices) < period + 1:
        return 50
    
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    
    if avg_loss == 0:
        return 100
    
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_macd(prices, fast=12, slow=26, signal=9):
    """Calcula MACD manualmente"""
    if len(prices) < slow:
        return 0, 0
    
    ema_fast = calculate_ema(prices, fast)
    ema_slow = calculate_ema(prices, slow)
    macd_line = ema_fast - ema_slow
    
    # Para o signal line, precisaríamos de mais dados
    return macd_line, 0

def calculate_bollinger_bands(prices, period=20, num_std=2):
    """Calcula Bollinger Bands manualmente"""
    if len(prices) < period:
        return np.nan, np.nan, np.nan
    
    sma = calculate_sma(prices, period)
    std = np.std(prices[-period:])
    
    upper_band = sma + (std * num_std)
    lower_band = sma - (std * num_std)
    
    return upper_band, sma, lower_band

def calculate_technical_indicators(prices):
    """Calcula todos os indicadores técnicos manualmente"""
    if len(prices) < 20:
        return {}
    
    try:
        sma_20 = calculate_sma(prices, 20)
        sma_50 = calculate_sma(prices, 50)
        ema_12 = calculate_ema(prices, 12)
        ema_26 = calculate_ema(prices, 26)
        rsi = calculate_rsi(prices)
        macd, macd_signal = calculate_macd(prices)
        bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(prices)
        
        return {
            'sma_20': float(sma_20) if not np.isnan(sma_20) else prices[-1],
            'sma_50': float(sma_50) if not np.isnan(sma_50) else prices[-1],
            'ema_12': float(ema_12) if not np.isnan(ema_12) else prices[-1],
            'ema_26': float(ema_26) if not np.isnan(ema_26) else prices[-1],
            'rsi': float(rsi) if not np.isnan(rsi) else 50,
            'macd': float(macd),
            'macd_signal': float(macd_signal),
            'bb_upper': float(bb_upper) if not np.isnan(bb_upper) else prices[-1],
            'bb_lower': float(bb_lower) if not np.isnan(bb_lower) else prices[-1]
        }
    except Exception as e:
        print(f"Erro no cálculo de indicadores: {e}")
        return {}

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
    macd_score = 1 if indicators['macd'] > 0 else -1
    
    # 4. Análise Bollinger Bands
    bb_score = 0
    if indicators['bb_upper'] > 0 and indicators['bb_lower'] > 0:
        bb_position = (current_price - indicators['bb_lower']) / (indicators['bb_upper'] - indicators['bb_lower'])
        if bb_position < 0.2:
            bb_score = 1  # Perto da banda inferior - potencial compra
        elif bb_position > 0.8:
            bb_score = -1  # Perto da banda superior - potencial venda
        analysis_results['bb_position'] = bb_position
    
    # Pontuação total
    total_score = trend_score + rsi_score + macd_score + bb_score
    
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
    
    analysis_results.update({
        'trend_score': trend_score,
        'rsi_score': rsi_score,
        'macd_score': macd_score,
        'bb_score': bb_score,
        'total_score': total_score,
        'rsi_value': indicators['rsi'],
        'macd_value': indicators['macd']
    })
    
    return direction, confidence, strength, analysis_results

def update_market_data():
    """Atualiza os dados do mercado"""
    while True:
        try:
            # Obter dados atualizados
            current_price, price_change, price_change_percent, price_history, success = get_bitcoin_data()
            
            if success and len(price_history) > 0:
                market_data['current_price'] = current_price
                market_data['price_change'] = price_change
                market_data['price_change_percent'] = price_change_percent
                market_data['history'] = price_history
                
                # Calcular indicadores técnicos
                indicators = calculate_technical_indicators(price_history)
                market_data['indicators'] = indicators
                
                # Fazer análise completa
                direction, confidence, strength, analysis = analyze_market_with_multiple_methods(
                    price_history, indicators
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
    current_price, _, _, price_history, _ = get_bitcoin_data()
    market_data['current_price'] = current_price
    market_data['history'] = price_history if price_history else [current_price] * 50
    
    print("🚀 Bitcoin Predictor Pro Iniciado!")
    app.run(debug=False, host='0.0.0.0', port=5000)