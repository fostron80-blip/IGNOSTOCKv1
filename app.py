import streamlit as st
import pandas as pd
import yfinance as yf
import FinanceDataReader as fdr
from datetime import datetime
import time

# --- [1. 페이지 설정 및 디자인] ---
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

# --- [2. 분석 핵심 클래스] ---
class StockAnalyzer:
    def __init__(self):
        self.sector_map = {
            "Technology": "기술", "Healthcare": "헬스케어", "Financial Services": "금융",
            "Consumer Cyclical": "경기소비재", "Industrials": "산업재", "Communication Services": "통신",
            "Consumer Defensive": "방어소비재", "Energy": "에너지", "Basic Materials": "기초소재",
            "Real Estate": "부동산", "Utilities": "유틸리티"
        }
        # KRX 리스팅 데이터 미리 로드 (실패 시 빈 데이터프레임)
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
        ma_list = [data.get(f'ma{p}', 0) for p in [9, 18, 27, 36, 54]]
        m9, m18, m27, m36, m54 = ma_list
        
        if t == 0: return "관망 😶🥱"
        if c < t and c < k and (m9 < m18 < m27) and (c < m9 < m18 < m27): return "🤬강력매도👎👎👎"
        if (m9 > m18 > m27) and c < m9: return "🤬지금당장매도👎👎"
        if c > t and c > k and (m9 > m18 > m27) and (c > m9 > m18 > m27): return "😎강력매수👍"
        if c > t and c > k and c > m9: return "😎매수👍"
        return "관망 😶🥱"

    def get_analysis(self, symbol, is_us):
        try:
            ticker_obj = yf.Ticker(symbol)
            info = ticker_obj.info
            
            # 데이터 로드 (일봉, 시간봉)
            df = ticker_obj.history(period="10y", interval="1d")
            if df.empty or len(df) < 10: return None
            
            df_hour = ticker_obj.history(period="60d", interval="1h")
            
            # 리샘플링
            m_df = df.resample('ME').last() 
            w_df = df.resample('W-MON').last() 
            s_df = df_hour.resample('2h').last().dropna() if not df_hour.empty else pd.DataFrame()
            
            curr_p = float(df['Close'].iloc[-1])

            def calc_signals(target_df):
                if target_df.empty or len(target_df) < 54: return {"t":0, "k":0, "c":0}
                t, k = self.get_ichimoku(target_df)
                c_s = target_df['Close']
                res = {"t": t, "k": k, "c": c_s.iloc[-1]}
                for p in [5, 9, 10, 15, 18, 20, 27, 36, 50, 54, 75]:
                    res[f"ma{p}"] = c_s.rolling(p).mean().iloc[-1]
                return res

            d_data, w_data, m_data = calc_signals(df), calc_signals(w_df), calc_signals(m_df)
            
            # 추세 판단 (핵심 로직)
            st_text, col = "💤관망", "#161A1E"
            dt, dk, wt, wk, mt, mk = d_data['t'], d_data['k'], w_data['t'], w_data['k'], m_data['t'], m_data['k']
            
            if curr_p > dt and curr_p > dk and curr_p > wt and curr_p > wk and curr_p > mt and curr_p > mk:
                st_text, col = "💎초강력 장기 롱", "#441A4D"
            elif curr_p > dt and curr_p > dk and curr_p > wt and curr_p > wk:
                st_text, col = "🔥강력 중기 롱", "#4D2A1A"
            elif curr_p < dt and curr_p < dk and curr_p < wt and curr_p < wk and curr_p < mt:
                st_text, col = "💀초강력 장기 숏", "#1A2D2D"

            return {
                "curr": curr_p, "marcap": info.get('marketCap', 0), 
                "st": st_text, "col": col, "d": d_data, "w": w_data, "m": m_data
            }
        except: return None

# --- [3. 메인 화면 구성] ---
analyzer = StockAnalyzer()
st.title("🚀 ignostock v1.0 - Web Dashboard")

m_choice = st.sidebar.radio("Market", ["KRX 전체", "KOSPI", "KOSDAQ", "USA"])
search_keyword = st.sidebar.text_input("🔍 종목명/티커 검색").strip().lower()

if st.button("📊 스캔 시작"):
    with st.spinner("데이터를 불러오는 중..."):
        try:
            # 시장별 데이터 로드 (KeyError 방지 로직)
            if "USA" in m_choice:
                df_raw = fdr.StockListing('NASDAQ')
                c_key = 'Symbol' if 'Symbol' in df_raw.columns else 'Code'
            else:
                df_raw = fdr.StockListing('KRX')
                c_key = 'Code' if 'Code' in df_raw.columns else 'Symbol'
            
            # 키워드 필터링
            if search_keyword:
                df_raw = df_raw[df_raw['Name'].str.lower().str.contains(search_keyword) | 
                                df_raw[c_key].str.lower().str.contains(search_keyword)]

            results = []
            table_area = st.empty()
            
            for i, (_, row) in enumerate(df_raw.head(50).iterrows()): # 속도를 위해 상위 50개 우선 스캔
                sym = str(row[c_key])
                if "USA" not in m_choice:
                    sym += ".KS" if row.get('Market') == 'KOSPI' else ".KQ"
                
                res = analyzer.get_analysis(sym, ("USA" in m_choice))
                if res:
                    m_val = res['marcap'] / 1e12
                    results.append({
                        "티커": sym.split('.')[0], "종목명": row['Name'], 
                        "시총": f"{m_val:.1f}조" if m_val > 1 else f"{m_val*10000:.0f}억",
                        "현재가": f"{res['curr']:,.0f}", "추세": res['st'],
                        "단기": analyzer.get_signal_text(res['d']),
                        "중기": analyzer.get_signal_text(res['w']),
                        "장기": analyzer.get_signal_text(res['m'])
                    })
                    table_area.dataframe(pd.DataFrame(results), use_container_width=True)
        except Exception as e:
            st.error(f"오류 발생: {e}. requirements.txt를 확인해 주세요.")
