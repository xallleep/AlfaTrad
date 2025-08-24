from flask import Flask, render_template, jsonify
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objs as go
import plotly.utils
import json
import requests
import time
import random

app = Flask(__name__)

# Configurações
SYMBOL = 'BTC-USD'

# Cache para dados
cache = {
    'btc_data': None,
    'last_update': None,
    'market_status': 'active'
}

# Simular dados de candle (como uma corretora)
def generate_candle_data():
    try:
        # Usar API do CoinGecko para dados reais
        url = "https://api.coingecko.com/api/v3/coins/bitcoin/ohlc"
        params = {
            'vs_currency': 'usd',
            'days': '1'
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        # Processar dados OHLC (Open, High, Low, Close)
        candles = []
        for candle in data:
            timestamp, open_price, high, low, close = candle
            candles.append({
                'timestamp': datetime.fromtimestamp(timestamp/1000),
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': random.uniform(1000, 5000)  # Volume simulado
            })
        
        df = pd.DataFrame(candles)
        df.set_index('timestamp', inplace=True)
        
        # Calcular indicadores
        df['SMA_20'] = df['close'].rolling(window=20).mean()
        df['SMA_50'] = df['close'].rolling(window=50).mean()
        
        # Calcular RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        print("Dados de candle gerados com sucesso!")
        return df
        
    except Exception as e:
        print(f"Erro ao buscar dados: {e}")
        return generate_fallback_data()

# Dados de fallback
def generate_fallback_data():
    print("Usando dados de fallback...")
    dates = pd.date_range(end=datetime.now(), periods=100, freq='5min')
    base_price = 40000
    prices = []
    
    # Gerar dados de candle realistas
    current_price = base_price
    for i in range(len(dates)):
        change = random.uniform(-100, 100)
        current_price += change
        open_price = current_price
        high = current_price + abs(random.uniform(50, 200))
        low = current_price - abs(random.uniform(50, 200))
        close = current_price + random.uniform(-50, 50)
        
        prices.append({
            'timestamp': dates[i],
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': random.uniform(1000, 5000)
        })
    
    df = pd.DataFrame(prices)
    df.set_index('timestamp', inplace=True)
    
    # Calcular indicadores
    df['SMA_20'] = df['close'].rolling(window=20).mean()
    df['SMA_50'] = df['close'].rolling(window=50).mean()
    
    return df

# Gerar previsão estilosa
def generate_prediction(data):
    if data is None or len(data) < 10:
        return None
    
    last_close = data['close'].iloc[-1]
    sma_20 = data['SMA_20'].iloc[-1] if not pd.isna(data['SMA_20'].iloc[-1]) else last_close
    sma_50 = data['SMA_50'].iloc[-1] if not pd.isna(data['SMA_50'].iloc[-1]) else last_close
    
    # Tendência baseada nas médias móveis
    trend_strength = 0
    if sma_20 > sma_50:
        trend_strength = (sma_20 - sma_50) / sma_50
    else:
        trend_strength = (sma_50 - sma_20) / sma_20
    
    # Gerar previsão com base na tendência
    predictions = []
    current = last_close
    
    for i in range(10):  # Prever próximos 10 pontos
        # Movimento baseado na tendência + algum ruído
        movement = trend_strength * random.uniform(0.5, 1.5) * 100
        if sma_20 < sma_50:  # Tendência de baixa
            movement = -movement
        
        current = current * (1 + movement / 10000)  # Pequenas variações
        predictions.append(current)
    
    return predictions

# Gerar sinal de trading
def generate_trading_signal(data, predictions):
    if data is None:
        return "NEUTRO", "gray", "Aguardando dados...", 50
    
    current_close = data['close'].iloc[-1]
    sma_20 = data['SMA_20'].iloc[-1] if not pd.isna(data['SMA_20'].iloc[-1]) else current_close
    sma_50 = data['SMA_50'].iloc[-1] if not pd.isna(data['SMA_50'].iloc[-1]) else current_close
    rsi = data['RSI'].iloc[-1] if 'RSI' in data and not pd.isna(data['RSI'].iloc[-1]) else 50
    
    # Lógica de sinal
    signals = []
    confidence = 50  # 0-100%
    
    # Tendência
    if sma_20 > sma_50:
        signals.append("Tendência ↗️")
        confidence += 15
    else:
        signals.append("Tendência ↘️")
        confidence -= 15
    
    # RSI
    if rsi > 70:
        signals.append("Sobrecomprado ⚠️")
        confidence -= 20
    elif rsi < 30:
        signals.append("Sobrevendido ⚡")
        confidence += 20
    
    # Previsão
    if predictions and len(predictions) > 0:
        predicted_change = (predictions[0] - current_close) / current_close * 100
        if abs(predicted_change) > 1:
            if predicted_change > 0:
                signals.append(f"Previsão: +{predicted_change:.1f}% 📈")
                confidence += 10
            else:
                signals.append(f"Previsão: {predicted_change:.1f}% 📉")
                confidence -= 10
    
    # Determinar sinal final
    confidence = max(0, min(100, confidence))  # Limitar entre 0-100
    
    if confidence >= 70:
        signal = "COMPRAR 🚀"
        color = "green"
    elif confidence <= 30:
        signal = "VENDER 🔻"
        color = "red"
    else:
        signal = "NEUTRO ⏸️"
        color = "gray"
    
    analysis = " | ".join(signals)
    return signal, color, analysis, confidence

# Rotas
@app.route('/')
def index():
    if cache['btc_data'] is None:
        cache['btc_data'] = generate_candle_data()
        cache['last_update'] = datetime.now()
    return render_template('index.html')

@app.route('/api/btc-data')
def btc_data():
    if cache['btc_data'] is None:
        cache['btc_data'] = generate_candle_data()
        cache['last_update'] = datetime.now()
    
    try:
        data = cache['btc_data']
        predictions = generate_prediction(data)
        signal, signal_color, analysis, confidence = generate_trading_signal(data, predictions)
        
        # Preparar dados para gráfico de candle
        dates = data.index.strftime('%Y-%m-%d %H:%M').tolist()
        opens = data['open'].round(2).tolist()
        highs = data['high'].round(2).tolist()
        lows = data['low'].round(2).tolist()
        closes = data['close'].round(2).tolist()
        
        # Gráfico de candle (como corretora)
        candle_fig = go.Figure()
        
        # Adicionar candles
        candle_fig.add_trace(go.Candlestick(
            x=dates,
            open=opens,
            high=highs,
            low=lows,
            close=closes,
            name='BTC/USD',
            increasing_line_color='#00C853',
            decreasing_line_color='#FF1744'
        ))
        
        # Adicionar médias móveis
        if 'SMA_20' in data:
            candle_fig.add_trace(go.Scatter(
                x=dates, y=data['SMA_20'].round(2).tolist(),
                name='SMA 20',
                line=dict(color='#FF9800', width=2)
            ))
        
        if 'SMA_50' in data:
            candle_fig.add_trace(go.Scatter(
                x=dates, y=data['SMA_50'].round(2).tolist(),
                name='SMA 50',
                line=dict(color='#2962FF', width=2)
            ))
        
        # Adicionar previsão
        if predictions:
            future_dates = [(datetime.now() + timedelta(minutes=5*i)).strftime('%Y-%m-%d %H:%M') for i in range(1, 11)]
            candle_fig.add_trace(go.Scatter(
                x=future_dates,
                y=[round(p, 2) for p in predictions],
                name='Previsão',
                line=dict(color='#FF00FF', width=3, dash='dot'),
                marker=dict(size=8)
            ))
        
        candle_fig.update_layout(
            title='BTC/USD - Gráfico de Candles em Tempo Real',
            xaxis_title='Data/Hora',
            yaxis_title='Preço (USD)',
            template='plotly_dark',
            height=600,
            showlegend=True,
            xaxis_rangeslider_visible=False
        )
        
        # Gráfico de RSI
        if 'RSI' in data:
            rsi_fig = go.Figure()
            rsi_fig.add_trace(go.Scatter(
                x=dates, y=data['RSI'].round(2).tolist(),
                name='RSI',
                line=dict(color='#BB86FC', width=2)
            ))
            rsi_fig.add_hline(y=70, line_dash="dash", line_color="red")
            rsi_fig.add_hline(y=30, line_dash="dash", line_color="green")
            rsi_fig.add_hline(y=50, line_dash="dot", line_color="gray")
            rsi_fig.update_layout(
                title='RSI - Índice de Força Relativa',
                height=250,
                template='plotly_dark'
            )
            rsi_graph = json.dumps(rsi_fig, cls=plotly.utils.PlotlyJSONEncoder)
        else:
            rsi_graph = None
        
        # Métricas
        current_price = closes[-1] if closes else 0
        prev_price = closes[-2] if len(closes) > 1 else current_price
        change = current_price - prev_price
        change_percent = (change / prev_price) * 100 if prev_price != 0 else 0
        
        return jsonify({
            'status': 'success',
            'candle_graph': json.dumps(candle_fig, cls=plotly.utils.PlotlyJSONEncoder),
            'rsi_graph': rsi_graph,
            'current_price': round(current_price, 2),
            'change': round(change, 2),
            'change_percent': round(change_percent, 2),
            'rsi': round(data['RSI'].iloc[-1], 2) if 'RSI' in data else 50,
            'signal': signal,
            'signal_color': signal_color,
            'analysis': analysis,
            'confidence': confidence,
            'last_update': cache['last_update'].strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        print(f"Erro: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/update')
def update_data():
    cache['btc_data'] = generate_candle_data()
    cache['last_update'] = datetime.now()
    return jsonify({'status': 'success', 'message': 'Dados atualizados'})

if __name__ == '__main__':
    cache['btc_data'] = generate_candle_data()
    cache['last_update'] = datetime.now()
    app.run(debug=False, host='0.0.0.0', port=5000)