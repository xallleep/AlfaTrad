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
    'market_status': 'loading'
}

# Função para buscar dados em tempo real
def fetch_realtime_data():
    try:
        # Buscar dados dos últimos 60 dias
        end_date = datetime.now()
        start_date = end_date - timedelta(days=60)
        
        # Formatar datas para o yfinance
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        # Buscar dados
        btc = yf.download(SYMBOL, start=start_str, end=end_str, progress=False)
        
        if btc.empty or len(btc) < 20:
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
        
        return btc
    except Exception as e:
        print(f"Erro ao buscar dados: {e}")
        return None

# Função para criar features para o modelo de ML
def create_features(data):
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

# Função para prever preços com ML
def predict_with_ml(data, days=7):
    try:
        # Preparar dados
        df = create_features(data)
        
        if len(df) < 30:
            return None
            
        # Features e target
        features = ['Close', 'SMA_20', 'SMA_50', 'RSI', 'MACD', 'Volatility', 
                   'Price_Change', 'Volume_Change', 'SMA_20_50_Ratio', 'BB_Position']
        
        X = df[features].values
        y = df['Close'].values
        
        # Normalizar dados
        scaler_X = StandardScaler()
        scaler_y = StandardScaler()
        
        X_scaled = scaler_X.fit_transform(X)
        y_scaled = scaler_y.fit_transform(y.reshape(-1, 1)).flatten()
        
        # Treinar modelo
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X_scaled, y_scaled)
        
        # Fazer previsões
        last_data = X_scaled[-1].reshape(1, -1)
        predictions_scaled = []
        
        for _ in range(days):
            pred = model.predict(last_data)[0]
            predictions_scaled.append(pred)
            
            # Atualizar last_data para a próxima previsão (simplificado)
            last_data = np.roll(last_data, -1)
            last_data[0, -1] = pred  # Atualizar apenas o último valor
        
        # Reverter a normalização
        predictions = scaler_y.inverse_transform(
            np.array(predictions_scaled).reshape(-1, 1)
        ).flatten()
        
        return predictions
    except Exception as e:
        print(f"Erro no modelo de ML: {e}")
        return None

# Função para gerar sinais de trading
def generate_signals(data, predictions):
    if data is None or predictions is None or len(data) < 20:
        return "NEUTRO", "gray", "Dados insuficientes para análise"
    
    current_price = data['Close'].iloc[-1]
    sma_20 = data['SMA_20'].iloc[-1]
    sma_50 = data['SMA_50'].iloc[-1]
    rsi = data['RSI'].iloc[-1]
    macd = data['MACD'].iloc[-1]
    
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
        if price_change > 2:
            signals.append(f"Previsão: +{price_change:.2f}%")
            confidence += 0.2
        elif price_change < -2:
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

# Atualizar dados em background
def update_data():
    while True:
        try:
            print("Atualizando dados do Bitcoin...")
            data = fetch_realtime_data()
            
            if data is not None and not data.empty:
                cache['btc_data'] = data
                cache['predictions'] = predict_with_ml(data)
                cache['last_update'] = datetime.now()
                cache['market_status'] = 'active'
                print(f"Dados atualizados em {cache['last_update']}")
            else:
                cache['market_status'] = 'error'
                print("Erro ao buscar dados")
                
        except Exception as e:
            print(f"Erro na atualização: {e}")
            cache['market_status'] = 'error'
        
        time.sleep(UPDATE_INTERVAL)

# Iniciar thread de atualização
update_thread = threading.Thread(target=update_data, daemon=True)
update_thread.start()

# Rotas
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/btc-data')
def btc_data():
    data = cache['btc_data']
    predictions = cache['predictions']
    
    if data is None or predictions is None:
        return jsonify({'status': 'loading'})
    
    # Preparar dados históricos
    dates = data.index.strftime('%Y-%m-%d').tolist()
    closes = data['Close'].round(2).fillna(0).tolist()
    volumes = data['Volume'].fillna(0).tolist()
    sma_20 = data['SMA_20'].round(2).fillna(0).tolist()
    sma_50 = data['SMA_50'].round(2).fillna(0).tolist()
    rsi = data['RSI'].round(2).fillna(50).tolist()
    
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

if __name__ == '__main__':
    # Buscar dados iniciais
    print("Iniciando aplicação...")
    print("Buscando dados iniciais do Bitcoin...")
    
    data = fetch_realtime_data()
    if data is not None and not data.empty:
        cache['btc_data'] = data
        cache['predictions'] = predict_with_ml(data)
        cache['last_update'] = datetime.now()
        cache['market_status'] = 'active'
        print("Dados iniciais carregados com sucesso!")
    else:
        print("Erro ao carregar dados iniciais")
    
    app.run(debug=False, host='0.0.0.0', port=5000)