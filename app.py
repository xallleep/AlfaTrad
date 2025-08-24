from flask import Flask, render_template, jsonify
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objs as go
import plotly.utils
import json
import threading
import time
import ta
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

app = Flask(__name__)

# Configurações
SYMBOL = 'BTC-USD'
UPDATE_INTERVAL = 300  # 5 minutos
PREDICTION_DAYS = 7

# Cache para dados
cache = {
    'btc_data': None,
    'last_update': None,
    'predictions': None,
    'market_status': 'loading',
    'initialized': False
}

# Função para buscar dados em tempo real
def fetch_realtime_data():
    try:
        # Buscar dados dos últimos 60 dias
        end_date = datetime.now()
        start_date = end_date - timedelta(days=60)
        
        # Buscar dados
        btc = yf.download(SYMBOL, start=start_date, end=end_date, progress=False)
        
        if btc.empty or len(btc) < 20:
            print("Dados vazios ou insuficientes")
            return None
            
        # Calcular indicadores técnicos
        btc['SMA_20'] = ta.trend.sma_indicator(btc['Close'], window=20)
        btc['SMA_50'] = ta.trend.sma_indicator(btc['Close'], window=50)
        btc['RSI'] = ta.momentum.rsi(btc['Close'], window=14)
        btc['MACD'] = ta.trend.macd_diff(btc['Close'])
        btc['BB_high'] = ta.volatility.bollinger_hband(btc['Close'])
        btc['BB_low'] = ta.volatility.bollinger_lband(btc['Close'])
        btc['Volatility'] = btc['Close'].rolling(window=20).std()
        
        # Calcular volume médio
        btc['Volume_MA'] = btc['Volume'].rolling(window=20).mean()
        
        print("Dados buscados com sucesso")
        return btc
    except Exception as e:
        print(f"Erro ao buscar dados: {e}")
        return None

# Função para criar features para o modelo de ML
def create_features(data):
    try:
        df = data.copy()
        
        # Features de momento
        df['Price_Change'] = df['Close'].pct_change()
        df['Volume_Change'] = df['Volume'].pct_change()
        
        # Features de médias móveis
        df['SMA_20_50_Ratio'] = df['SMA_20'] / df['SMA_50']
        
        # Features de volatilidade
        df['Volatility_Change'] = df['Volatility'].pct_change()
        
        # Features de Bollinger Bands
        df['BB_Position'] = (df['Close'] - df['BB_low']) / (df['BB_high'] - df['BB_low'])
        
        # Remover valores NaN
        df = df.dropna()
        
        return df
    except Exception as e:
        print(f"Erro ao criar features: {e}")
        return data

# Função de previsão simplificada (sem ML para evitar problemas no Render)
def predict_prices(data, days=7):
    try:
        if data is None or len(data) < 10:
            return None
        
        # Previsão simples baseada na tendência recente
        recent_prices = data['Close'].tail(10).values
        avg_change = np.mean(np.diff(recent_prices) / recent_prices[:-1])
        
        predictions = []
        current = recent_prices[-1]
        
        for _ in range(days):
            # Adicionar uma variação baseada na tendência média
            change = current * avg_change if not np.isnan(avg_change) else current * 0.001
            current = current + change
            predictions.append(current)
        
        return predictions
    except Exception as e:
        print(f"Erro na previsão: {e}")
        return None

# Função para gerar sinais de trading
def generate_signals(data, predictions):
    if data is None or predictions is None or len(data) < 20:
        return "NEUTRO", "gray", "Aguardando dados..."
    
    try:
        current_price = data['Close'].iloc[-1]
        sma_20 = data['SMA_20'].iloc[-1] if 'SMA_20' in data and not pd.isna(data['SMA_20'].iloc[-1]) else current_price
        sma_50 = data['SMA_50'].iloc[-1] if 'SMA_50' in data and not pd.isna(data['SMA_50'].iloc[-1]) else current_price
        rsi = data['RSI'].iloc[-1] if 'RSI' in data and not pd.isna(data['RSI'].iloc[-1]) else 50
        macd = data['MACD'].iloc[-1] if 'MACD' in data and not pd.isna(data['MACD'].iloc[-1]) else 0
        
        # Lógica de sinal
        signals = []
        confidence = 0
        
        # Tendência de preço
        if not np.isnan(sma_20) and not np.isnan(sma_50):
            if current_price > sma_20 > sma_50:
                signals.append("Tendência de alta")
                confidence += 0.3
            elif current_price < sma_20 < sma_50:
                signals.append("Tendência de baixa")
                confidence -= 0.3
        
        # RSI
        if not np.isnan(rsi):
            if rsi < 30:
                signals.append("RSI indica sobrevenda")
                confidence += 0.2
            elif rsi > 70:
                signals.append("RSI indica sobrecompra")
                confidence -= 0.2
        
        # MACD
        if not np.isnan(macd):
            if macd > 0:
                signals.append("MACD positivo")
                confidence += 0.1
            else:
                signals.append("MACD negativo")
                confidence -= 0.1
        
        # Previsão de preço
        if predictions is not None and len(predictions) > 0:
            price_change = (predictions[0] - current_price) / current_price * 100
            if abs(price_change) > 1:  # Só considerar se mudança > 1%
                if price_change > 0:
                    signals.append(f"Previsão: +{price_change:.2f}%")
                    confidence += 0.2
                else:
                    signals.append(f"Previsão: {price_change:.2f}%")
                    confidence -= 0.2
        
        # Determinar sinal final
        if confidence >= 0.3:
            signal = "COMPRAR"
            color = "green"
        elif confidence <= -0.3:
            signal = "VENDER"
            color = "red"
        else:
            signal = "NEUTRO"
            color = "gray"
        
        # Gerar mensagem de análise
        analysis_msg = " | ".join(signals) if signals else "Mercado estável"
        
        return signal, color, analysis_msg
    except Exception as e:
        print(f"Erro ao gerar sinais: {e}")
        return "NEUTRO", "gray", "Erro na análise"

# Carregar dados iniciais
def load_initial_data():
    try:
        print("Carregando dados iniciais...")
        data = fetch_realtime_data()
        
        if data is not None and not data.empty:
            cache['btc_data'] = data
            cache['predictions'] = predict_prices(data)
            cache['last_update'] = datetime.now()
            cache['market_status'] = 'active'
            cache['initialized'] = True
            print("Dados iniciais carregados com sucesso!")
        else:
            cache['market_status'] = 'error'
            print("Erro ao carregar dados iniciais")
    except Exception as e:
        print(f"Erro no carregamento inicial: {e}")
        cache['market_status'] = 'error'

# Rotas
@app.route('/')
def index():
    # Garantir que os dados estão carregados
    if not cache['initialized']:
        load_initial_data()
    return render_template('index.html')

@app.route('/api/btc-data')
def btc_data():
    # Se não há dados, tentar carregar
    if cache['btc_data'] is None:
        load_initial_data()
    
    if cache['btc_data'] is None:
        return jsonify({'status': 'loading'})
    
    try:
        data = cache['btc_data']
        predictions = cache['predictions']
        
        # Preparar dados históricos
        dates = data.index.strftime('%Y-%m-%d').tolist()
        closes = data['Close'].round(2).fillna(0).tolist()
        volumes = data['Volume'].fillna(0).tolist()
        sma_20 = data['SMA_20'].round(2).fillna(closes[-1] if closes else 0).tolist() if 'SMA_20' in data else closes
        sma_50 = data['SMA_50'].round(2).fillna(closes[-1] if closes else 0).tolist() if 'SMA_50' in data else closes
        rsi = data['RSI'].round(2).fillna(50).tolist() if 'RSI' in data else [50] * len(closes)
        
        # Gerar datas para previsão
        last_date = data.index[-1]
        prediction_dates = [(last_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(1, 8)]
        
        # Gerar sinais
        signal, signal_color, analysis = generate_signals(data, predictions)
        
        # Criar gráfico de preço
        price_fig = go.Figure()
        price_fig.add_trace(go.Scatter(x=dates, y=closes, mode='lines', name='Preço', line=dict(color='#17BECF')))
        price_fig.add_trace(go.Scatter(x=dates, y=sma_20, mode='lines', name='SMA 20', line=dict(color='#FF7F0E', dash='dash')))
        price_fig.add_trace(go.Scatter(x=dates, y=sma_50, mode='lines', name='SMA 50', line=dict(color='#2CA02C', dash='dash')))
        
        # Adicionar previsões se disponíveis
        if predictions is not None and len(predictions) > 0:
            price_fig.add_trace(go.Scatter(
                x=prediction_dates, 
                y=[round(p, 2) for p in predictions[:7]], 
                mode='lines+markers', 
                name='Previsão', 
                line=dict(color='#D62728', dash='dot')
            ))
        
        price_fig.update_layout(
            title='Bitcoin - Preço e Previsão',
            xaxis_title='Data',
            yaxis_title='Preço (USD)',
            template='plotly_dark',
            hovermode='x unified',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#FFF')
        )
        price_graph = json.dumps(price_fig, cls=plotly.utils.PlotlyJSONEncoder)
        
        # Criar gráfico de RSI
        rsi_fig = go.Figure()
        rsi_fig.add_trace(go.Scatter(x=dates, y=rsi, mode='lines', name='RSI', line=dict(color='#9467BD')))
        rsi_fig.add_hline(y=70, line_dash="dash", line_color="red")
        rsi_fig.add_hline(y=30, line_dash="dash", line_color="green")
        rsi_fig.update_layout(
            title='RSI - Índice de Força Relativa',
            xaxis_title='Data',
            yaxis_title='RSI',
            template='plotly_dark',
            hovermode='x unified',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#FFF'),
            height=300
        )
        rsi_graph = json.dumps(rsi_fig, cls=plotly.utils.PlotlyJSONEncoder)
        
        # Calcular métricas atuais
        current_price = closes[-1] if closes else 0
        prev_close = closes[-2] if len(closes) > 1 else current_price
        change = current_price - prev_close
        change_percent = (change / prev_close) * 100 if prev_close != 0 else 0
        
        # Volume atual
        current_volume = volumes[-1] if volumes else 0
        avg_volume = data['Volume_MA'].iloc[-1] if 'Volume_MA' in data and not pd.isna(data['Volume_MA'].iloc[-1]) else current_volume
        volume_change_pct = ((current_volume - avg_volume) / avg_volume * 100) if avg_volume != 0 else 0
        
        return jsonify({
            'status': 'success',
            'price_graph': price_graph,
            'rsi_graph': rsi_graph,
            'current_price': round(current_price, 2),
            'change': round(change, 2),
            'change_percent': round(change_percent, 2),
            'volume': current_volume,
            'volume_change': round(volume_change_pct, 2),
            'rsi': round(rsi[-1], 2) if rsi else 50,
            'signal': signal,
            'signal_color': signal_color,
            'analysis': analysis,
            'last_update': cache['last_update'].strftime('%Y-%m-%d %H:%M:%S') if cache['last_update'] else 'N/A',
            'next_update': (cache['last_update'] + timedelta(seconds=UPDATE_INTERVAL)).strftime('%Y-%m-%d %H:%M:%S') if cache['last_update'] else 'N/A'
        })
    except Exception as e:
        print(f"Erro na API: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

# Health check para o Render
@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'initialized': cache['initialized']})

# Inicializar dados quando o app iniciar
with app.app_context():
    load_initial_data()

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)