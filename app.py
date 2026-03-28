import streamlit as st
import pandas as pd
import yfinance as yf
import FinanceDataReader as fdr
from datetime import datetime
import time

# --- [1. 페이지 설정 및 CSS] ---
st.set_page_config(page_title="ignostock v1.0", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0F1115; }
    div.stButton > button {
        font-weight: bold; border-radius: 5px; height: 35px; width: 100%;
    }
    .stProgress > div > div > div > div { background-color: #F0B90B; }
    </style>
    """, unsafe_allow_html=True)

# --- [2. 핵심 분석 클래스] ---
class StockAnalyzer:
    def __init__(self):
        self.sector_map = {
            "Technology": "기술", "Healthcare": "헬스케어", "Financial Services": "금융",
            "Consumer Cyclical": "경기소비재", "Industrials": "산업재", "Communication Services": "통신",
            "Consumer Defensive": "방어소비재", "Energy": "에너지", "Basic Materials": "기초소재",
            "Real Estate": "부동산", "Utilities": "유틸리티"
        }
        # KRX 리스팅 안전 로드 (ValueError 방지)
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
        m9, m18, m27 = data.get('ma9', 0), data.get('ma18', 0), data.get('ma27', 0)
        if t == 0: return "관망 😶🥱"
        if c > t and c > k and (m9 > m18 > m27): return "😎강력매수👍"
        if c < t and c < k and (m9 < m18 < m27): return "🤬강력매도👎"
        return "관망 😶🥱"

    def get_analysis(self, symbol, is_us):
        try:
            ticker_obj = yf.Ticker(symbol)
            # info 호출 실패 시 기본값 설정
            try:
                info = ticker_obj.info
                marcap = info.get('marketCap', 0)
                raw_sector = info.get('sector', 'N/A')
            except:
                marcap, raw_sector = 0, 'N/A'

            df = ticker_obj.history(period="10y", interval="1d")
            if df.empty or len(df) < 30: return None
            
            curr_p = float(df['Close'].iloc[-1])
            prev_p = float(df['Close'].iloc[-2]) if len(df) > 1 else curr_p
            
            w_df = df.resample('W-MON').last()
            m_df = df.resample('ME').last()

            def calc(target_df):
                if len(target_df) < 27: return {"t":0, "k":0, "c":0}
                t, k = self.get_ichimoku(target_df)
                res = {"t": t, "k": k, "c": target_df['Close'].iloc[-1]}
                for p in [9, 18, 27]:
                    res[f"ma{p}"] = target_df['Close'].rolling(p).mean().iloc[-1]
                return res

            return {
                "curr": curr_p, "prev": prev_p, "marcap": marcap,
                "sector": self.sector_map.get(raw_sector, raw_sector),
                "d": calc(df), "w": calc(w_df), "m": calc(m_df),
                "st": "💎롱" if curr_p > calc(df)['t'] else "💤관망"
            }
        except: return None

# --- [3. UI 및 제어] ---
analyzer = StockAnalyzer()
st.sidebar.title("ignostock v1.0")
m_choice = st.sidebar.radio("Market", ["KOSPI", "KOSDAQ", "USA", "KRX 전체"])
search_keyword = st.sidebar.text_input("🔍 종목명/티커 검색").strip().lower()

if st.button("🚀 스캔 시작"):
    targets = []
    with st.spinner("📡 목록 동기화 중..."):
        try:
            # 시장별 리스팅 및 열 이름 자동 처리 (KeyError 방지)
            if m_choice == "USA":
                df_raw = fdr.StockListing('NASDAQ')
            else:
                df_raw = fdr.StockListing('KRX')
            
            # 'Symbol' 또는 'Code' 열 자동 감지
            c_key = 'Symbol' if 'Symbol' in df_raw.columns else 'Code'
            
            if search_keyword:
                df_raw = df_raw[df_raw['Name'].str.lower().str.contains(search_keyword, na=False) | 
                                df_raw[c_key].str.lower().str.contains(search_keyword, na=False)]
            
            for _, row in df_raw.head(50).iterrows(): # 속도를 위해 50개 제한
                sym = str(row[c_key])
                if m_choice != "USA":
                    sym += ".KS" if row.get('Market') == 'KOSPI' else ".KQ"
                targets.append((sym, row['Name'], row.get('Market', 'US')))
        except Exception as e:
            st.error(f"데이터 로드 실패 (KRX 서버 확인): {e}") #

    results = []
    table_placeholder = st.empty()
    
    for i, (symbol, name, market) in enumerate(targets):
        data = analyzer.get_analysis(symbol, (market == "US"))
        if data:
            results.append({
                "티커": symbol.split('.')[0], "종목명": name,
                "현재가": f"{data['curr']:,.0f}",
                "단기": analyzer.get_signal_text(data['d']),
                "중기": analyzer.get_signal_text(data['w']),
                "장기": analyzer.get_signal_text(data['m'])
            })
            table_placeholder.dataframe(pd.DataFrame(results), use_container_width=True)
