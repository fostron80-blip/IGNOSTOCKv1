import streamlit as st
import pandas as pd
import yfinance as yf
import FinanceDataReader as fdr
from datetime import datetime

# --- [1. 페이지 설정] ---
st.set_page_config(page_title="ignostock v1.0", layout="wide")

# --- [2. 분석 핵심 클래스] ---
class StockAnalyzer:
    def __init__(self):
        # KRX 리스팅 데이터 미리 로드 (실패 시 빈 데이터프레임으로 방어)
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
            df = ticker_obj.history(period="10y", interval="1d")
            if df.empty or len(df) < 10: return None
            
            m_df = df.resample('ME').last() 
            w_df = df.resample('W-MON').last() 
            curr_p = float(df['Close'].iloc[-1])

            def calc_signals(target_df):
                if target_df.empty or len(target_df) < 27: return {"t":0, "k":0, "c":0}
                t, k = self.get_ichimoku(target_df)
                res = {"t": t, "k": k, "c": target_df['Close'].iloc[-1]}
                for p in [9, 18, 27]:
                    res[f"ma{p}"] = target_df['Close'].rolling(p).mean().iloc[-1]
                return res

            return {
                "curr": curr_p, "marcap": ticker_obj.info.get('marketCap', 0),
                "d": calc_signals(df), "w": calc_signals(w_df), "m": calc_signals(m_df)
            }
        except: return None

# --- [3. 메인 UI] ---
analyzer = StockAnalyzer()
st.title("🚀 ignostock v1.0")

m_choice = st.sidebar.radio("Market", ["KRX 전체", "KOSPI", "KOSDAQ", "USA"])

if st.button("📊 스캔 시작"):
    try:
        # 시장별 열 이름 불일치 해결 (KeyError 방지)
        if "USA" in m_choice:
            df_raw = fdr.StockListing('NASDAQ')
            c_key = 'Symbol' if 'Symbol' in df_raw.columns else 'Code'
        else:
            df_raw = fdr.StockListing('KRX')
            c_key = 'Code' if 'Code' in df_raw.columns else 'Symbol'

        results = []
        table_area = st.empty()
        
        for i, (_, row) in enumerate(df_raw.head(30).iterrows()): # 테스트를 위해 30개 제한
            sym = str(row[c_key])
            if "USA" not in m_choice:
                sym += ".KS" if row.get('Market') == 'KOSPI' else ".KQ"
            
            res = analyzer.get_analysis(sym, ("USA" in m_choice))
            if res:
                results.append({
                    "티커": sym.split('.')[0], "종목명": row['Name'], 
                    "현재가": f"{res['curr']:,.0f}", 
                    "단기": analyzer.get_signal_text(res['d']),
                    "중기": analyzer.get_signal_text(res['w']),
                    "장기": analyzer.get_signal_text(res['m'])
                })
                table_area.dataframe(pd.DataFrame(results), use_container_width=True)
    except Exception as e:
        st.error(f"오류 발생: {e}")
