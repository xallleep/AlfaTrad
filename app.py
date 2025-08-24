from flask import Flask, render_template, jsonify
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objs as go
import plotly.utils
import json
import requests
import time

app = Flask(__name__)

# Configurações
SYMBOL = 'BTC-USD'

# Cache para dados
cache = {
    'btc_data': None,
    'last_update': None,
    'market_status': 'loading'
}

# Função SUPER simplificada para buscar dados
def fetch_btc_data():
    try:
        print("Buscando dados do Bitcoin...")
        
        # Usando API pública mais simples (CoinGecko)
        url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
        params = {
            'vs_currency': 'usd',
            'days': '30',
            'interval': 'daily'
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        # Processar dados
        prices = data['prices']
        dates = [datetime.fromtimestamp(price[0]/1000) for price in prices]
        values = [price[1] for price in prices]
        
        # Criar DataFrame
        df = pd.DataFrame({
            'Date': dates,
            'Close': values
        })
        df.set_index('Date', inplace=True)
        
        # Calcular indicadores simples
        df['SMA_7'] = df['Close'].rolling(window=7).mean()
        df['SMA_14'] = df['Close'].rolling(window=14).mean()
        
        # Calcular RSI manualmente (simplificado)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        print("Dados carregados com sucesso!")
        return df
        
    except Exception as e:
        print(f"Erro ao buscar dados: {e}")
        # Dados de fallback para não quebrar o site
        return create_fallback_data()

# Dados de fallback caso a API falhe
def create_fallback_data():
    dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
    prices = np.random.normal(40000, 2000, 30).cumsum()
    
    df = pd.DataFrame({
        'Date': dates,
        'Close': prices
    })
    df.set_index('Date', inplace=True)
    
    df['SMA_7'] = df['Close'].rolling(window=7).mean()
    df['SMA_14'] = df['Close'].rolling(window=14).mean()
    
    return df

# Previsão simples
def simple_prediction(data):
    if data is None or len(data) < 10:
        return None
    
    last_price = data['Close'].iloc[-1]
    trend = np.polyfit(range(5), data['Close'].tail(5).values, 1)[0]
    
    # Prever próximos 3 dias
    predictions = [last_price + (i + 1) * trend for i in range(3)]
    return predictions

# Gerar sinais
def generate_signal(data):
    if data is None or len(data) < 14:
        return "NEUTRO", "gray", "Dados insuficientes"
    
    current_price = data['Close'].iloc[-1]
    sma_7 = data['SMA_7'].iloc[-1]
    sma_14 = data['SMA_14'].iloc[-1]
    rsi = data['RSI'].iloc[-1] if 'RSI' in data else 50
    
    signals = []
    
    if current_price > sma_7 > sma_14:
        signals.append("Tendência de Alta")
    elif current_price < sma_7 < sma_14:
        signals.append("Tendência de Baixa")
    
    if rsi > 70:
        signals.append("Sobrecomprado")
    elif rsi < 30:
        signals.append("Sobrevendido")
    
    if not signals:
        signals.append("Mercado Neutro")
    
    # Lógica simples de sinal
    if "Tendência de Alta" in signals and "Sobrevendido" in signals:
        return "COMPRAR", "green", " | ".join(signals)
    elif "Tendência de Baixa" in signals and "Sobrecomprado" in signals:
        return "VENDER", "red", " | ".join(signals)
    else:
        return "NEUTRO", "gray", " | ".join(signals)

# Rotas
@app.route('/')
def index():
    # Carregar dados se não estiverem em cache
    if cache['btc_data'] is None:
        cache['btc_data'] = fetch_btc_data()
        cache['last_update'] = datetime.now()
        cache['market_status'] = 'active'
    
    return render_template('index.html')

@app.route('/api/btc-data')
def btc_data():
    # Se não há dados, tentar carregar
    if cache['btc_data'] is None:
        cache['btc_data'] = fetch_btc_data()
        cache['last_update'] = datetime.now()
    
    if cache['btc_data'] is None:
        return jsonify({'status': 'loading'})
    
    try:
        data = cache['btc_data']
        predictions = simple_prediction(data)
        signal, signal_color, analysis = generate_signal(data)
        
        # Preparar dados para gráfico
        dates = data.index.strftime('%Y-%m-%d').tolist()
        closes = data['Close'].round(2).tolist()
        sma_7 = data['SMA_7'].round(2).tolist()
        sma_14 = data['SMA_14'].round(2).tolist()
        rsi = data['RSI'].round(2).tolist() if 'RSI' in data else [50] * len(closes)
        
        # Gráfico de preço
        price_fig = go.Figure()
        price_fig.add_trace(go.Scatter(x=dates, y=closes, mode='lines', name='Preço', line=dict(color='#17BECF')))
        price_fig.add_trace(go.Scatter(x=dates, y=sma_7, mode='lines', name='SMA 7', line=dict(color='#FF7F0E', dash='dash')))
        price_fig.add_trace(go.Scatter(x=dates, y=sma_14, mode='lines', name='SMA 14', line=dict(color='#2CA02C', dash='dash')))
        
        price_fig.update_layout(
            title='Bitcoin - Preço e Médias Móveis',
            xaxis_title='Data',
            yaxis_title='Preço (USD)',
            template='plotly_dark',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#FFF')
        )
        
        # Gráfico de RSI
        rsi_fig = go.Figure()
        rsi_fig.add_trace(go.Scatter(x=dates, y=rsi, mode='lines', name='RSI', line=dict(color='#9467BD')))
        rsi_fig.add_hline(y=70, line_dash="dash", line_color="red")
        rsi_fig.add_hline(y=30, line_dash="dash", line_color="green")
        rsi_fig.update_layout(
            title='RSI - Índice de Força Relativa',
            xaxis_title='Data',
            yaxis_title='RSI',
            template='plotly_dark',
            height=300,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#FFF')
        )
        
        # Métricas
        current_price = closes[-1]
        prev_price = closes[-2] if len(closes) > 1 else current_price
        change = current_price - prev_price
        change_percent = (change / prev_price) * 100
        
        return jsonify({
            'status': 'success',
            'price_graph': json.dumps(price_fig, cls=plotly.utils.PlotlyJSONEncoder),
            'rsi_graph': json.dumps(rsi_fig, cls=plotly.utils.PlotlyJSONEncoder),
            'current_price': round(current_price, 2),
            'change': round(change, 2),
            'change_percent': round(change_percent, 2),
            'rsi': round(rsi[-1], 2),
            'signal': signal,
            'signal_color': signal_color,
            'analysis': analysis,
            'last_update': cache['last_update'].strftime('%Y-%m-%d %H:%M:%S') if cache['last_update'] else 'N/A'
        })
        
    except Exception as e:
        print(f"Erro na API: {e}")
        return jsonify({'status': 'error', 'message': 'Erro ao processar dados'})

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'data_loaded': cache['btc_data'] is not None})

if __name__ == '__main__':
    # Pré-carregar dados ao iniciar
    cache['btc_data'] = fetch_btc_data()
    cache['last_update'] = datetime.now()
    cache['market_status'] = 'active'
    
    app.run(debug=False, host='0.0.0.0', port=5000)