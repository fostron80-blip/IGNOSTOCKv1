import streamlit as st
import pandas as pd
import yfinance as yf
import FinanceDataReader as fdr
from datetime import datetime

# --- [1. 페이지 설정 및 디자인] ---
st.set_page_config(page_title="ignostock v1.0", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0F1115; }
    div.stButton > button { font-weight: bold; border-radius: 5px; width: 100%; }
    </style>
    """, unsafe_allow_html=True)

# --- [2. 분석 핵심 클래스] ---
class StockAnalyzer:
    def __init__(self):
        # KRX 리스팅 로드 실패 시 빈 데이터프레임으로 에러 방지
        try:
            self.krx_listing = fdr.StockListing('KRX')
        except:
            self.krx_listing = pd.DataFrame()

    def get_ichimoku(self, df):
        if len(df) < 26: return 0, 0
        t = (df['High'].rolling(9).max() + df['Low'].rolling(9).min()) / 2
        k = (df['High'].rolling(26).max() + df['Low'].rolling(26).min()) / 2
        return t.iloc[-1], k.iloc[-1]

    def get_signal_text(self, data):
        c, t, k = data.get('c', 0), data.get('t', 0), data.get('k', 0)
        if t == 0: return "관망 😶"
        if c > t and c > k: return "😎매수👍"
        if c < t and c < k: return "🤬매도👎"
        return "관망 😶"

    def get_analysis(self, symbol):
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="10y", interval="1d")
            if df.empty or len(df) < 26: return None
            
            w_df = df.resample('W-MON').last()
            
            def calc(target_df):
                t, k = self.get_ichimoku(target_df)
                return {"t": t, "k": k, "c": target_df['Close'].iloc[-1]}

            return {"curr": df['Close'].iloc[-1], "d": calc(df), "w": calc(w_df)}
        except: return None

# --- [3. 메인 화면] ---
analyzer = StockAnalyzer()
st.title("🚀 ignostock v1.0 - Web Dashboard")

m_choice = st.sidebar.radio("Market", ["KRX 전체", "KOSPI", "KOSDAQ", "USA"])

if st.button("📊 스캔 시작"):
    with st.spinner("데이터 로드 중..."):
        try:
            # 시장별 리스팅 (KeyError: 'Symbol' 해결 로직)
            if "USA" in m_choice:
                df_raw = fdr.StockListing('NASDAQ')
                col_name = 'Symbol' if 'Symbol' in df_raw.columns else 'Code'
            else:
                df_raw = fdr.StockListing('KRX')
                col_name = 'Code' if 'Code' in df_raw.columns else 'Symbol'
            
            results = []
            table_area = st.empty()
            
            # 상위 30개 종목 우선 스캔
            for _, row in df_raw.head(30).iterrows():
                sym = str(row[col_name])
                if "USA" not in m_choice:
                    sym += ".KS" if row.get('Market') == 'KOSPI' else ".KQ"
                
                res = analyzer.get_analysis(sym)
                if res:
                    results.append({
                        "티커": sym.split('.')[0], "종목명": row['Name'],
                        "현재가": f"{res['curr']:,.0f}",
                        "단기신호": analyzer.get_signal_text(res['d']),
                        "중기신호": analyzer.get_signal_text(res['w'])
                    })
                    table_area.dataframe(pd.DataFrame(results), use_container_width=True)
        except Exception as e:
            st.error(f"목록 로드 중 오류 발생: {e}")
