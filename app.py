import streamlit as st
import pandas as pd
import yfinance as yf
import FinanceDataReader as fdr
from datetime import datetime, timedelta

# --- [1. 페이지 설정 및 성능 최적화] ---
st.set_page_config(page_title="ignostock v1.0", layout="wide")

# 캐싱 기능을 사용하여 시장 리스트를 한 번만 불러오도록 설정
@st.cache_data(ttl=3600)  # 1시간 동안 캐시 유지
def get_cached_listing(market):
    try:
        df = fdr.StockListing(market)
        # 열 이름 표준화 (Code 또는 Symbol 대응)
        if 'Symbol' not in df.columns and 'Code' in df.columns:
            df = df.rename(columns={'Code': 'Symbol'})
        return df
    except:
        return pd.DataFrame()

# --- [2. 핵심 분석 클래스] ---
class StockAnalyzer:
    def __init__(self):
        self.sector_map = {
            "Technology": "기술", "Healthcare": "헬스케어", "Financial Services": "금융",
            "Consumer Cyclical": "경기소비재", "Industrials": "산업재", "Communication Services": "통신",
            "Consumer Defensive": "방어소비재", "Energy": "에너지", "Basic Materials": "기초소재",
            "Real Estate": "부동산", "Utilities": "유틸리티"
        }

    def get_ichimoku(self, df):
        if len(df) < 26: return 0, 0
        # 일목균형표 전환선(9), 기준선(26) 계산
        t = (df['High'].rolling(9).max() + df['Low'].rolling(9).min()) / 2
        k = (df['High'].rolling(26).max() + df['Low'].rolling(26).min()) / 2
        return t.iloc[-1], k.iloc[-1]

    def get_signal_text(self, data):
        c, t, k = data.get('c', 0), data.get('t', 0), data.get('k', 0)
        m9, m18, m27 = data.get('ma9', 0), data.get('ma18', 0), data.get('ma27', 0)
        
        if t == 0 or k == 0: return "관망 😶🥱"
        
        # 매수/매도 시그널 로직 (제공된 로직 기반 요약)
        if c > t and c > k and (m9 > m18 > m27): return "😎강력매수👍"
        if c < t and c < k and (m9 < m18 < m27): return "🤬강력매도👎"
        return "관망 😶🥱"

    def get_analysis(self, symbol, is_us):
        try:
            ticker_obj = yf.Ticker(symbol)
            
            # 1. 시세 데이터 먼저 가져오기 (Fastest)
            # period를 10y 대신 분석에 필요한 최소한의 기간(예: 2y)으로 줄이면 속도가 더 빠릅니다.
            df = ticker_obj.history(period="2y", interval="1d")
            if df.empty or len(df) < 60: return None
            
            # 2. 기업 정보 가져오기 (Slowest - 예외처리 필수)
            try:
                info = ticker_obj.info
                marcap = info.get('marketCap', 0) or 0
                raw_sector = info.get('sector', 'N/A')
            except:
                marcap, raw_sector = 0, 'N/A'

            curr_p = float(df['Close'].iloc[-1])
            
            # 주봉, 월봉 리샘플링
            w_df = df.resample('W-MON').last()
            m_df = df.resample('ME').last()

            def calc_signals(target_df):
                if len(target_df) < 27: return {"t":0, "k":0, "c":0}
                t, k = self.get_ichimoku(target_df)
                res = {"t": t, "k": k, "c": target_df['Close'].iloc[-1]}
                for p in [9, 18, 27]:
                    res[f"ma{p}"] = target_df['Close'].rolling(p).mean().iloc[-1]
                return res

            d_data = calc_signals(df)
            w_data = calc_signals(w_df)
            m_data = calc_signals(m_df)

            # 추세 판별 (간략화된 예시)
            st_text = "💤관망"
            if curr_p > d_data['t'] and curr_p > d_data['k']:
                st_text = "📈 롱"
                if curr_p > w_data['t'] and curr_p > m_data['t']:
                    st_text = "💎 초강력 장기 롱"

            return {
                "curr": curr_p, "marcap": marcap, "st": st_text,
                "d": d_data, "w": w_data, "m": m_data,
                "sector": self.sector_map.get(raw_sector, raw_sector)
            }
        except:
            return None

# --- [3. 메인 UI] ---
analyzer = StockAnalyzer()
st.sidebar.title("ignostock v1.0")

m_choice = st.sidebar.selectbox("Market", ["KRX 전체", "KOSPI", "KOSDAQ", "USA"])
search_keyword = st.sidebar.text_input("🔍 종목명/티커 검색").strip().lower()

if st.button("🚀 스캔 시작"):
    with st.spinner("📡 데이터 동기화 중..."):
        # 시장 데이터 로드
        if m_choice == "USA":
            df_raw = get_cached_listing('NASDAQ')
        else:
            df_raw = get_cached_listing('KRX')
            if m_choice != "KRX 전체":
                df_raw = df_raw[df_raw['Market'] == m_choice]

        if search_keyword:
            df_raw = df_raw[df_raw['Name'].str.lower().str.contains(search_keyword, na=False) | 
                            df_raw['Symbol'].str.lower().str.contains(search_keyword, na=False)]

    if df_raw.empty:
        st.warning("검색 결과가 없습니다.")
    else:
        results = []
        table_area = st.empty()
        pbar = st.progress(0)
        
        # 성능을 위해 상위 50개만 우선 스캔 (필요시 조절)
        target_list = df_raw.head(50)
        
        for i, (_, row) in enumerate(target_list.iterrows()):
            sym = str(row['Symbol'])
            if m_choice != "USA":
                sym += ".KS" if row.get('Market') == 'KOSPI' else ".KQ"
            
            res = analyzer.get_analysis(sym, (m_choice == "USA"))
            if res:
                # 시가총액 계산
                m_val = (res['marcap'] * (1350.0 if m_choice == "USA" else 1.0)) / 1e12
                marcap_str = f"{m_val:,.1f}조" if m_val >= 1 else f"{m_val*10000:,.0f}억"
                
                results.append({
                    "티커": sym.split('.')[0], 
                    "종목명": row['Name'], 
                    "시가총액": marcap_str,
                    "현재가": f"{res['curr']:,.0f}", 
                    "추세": res['st'],
                    "단기": analyzer.get_signal_text(res['d']), 
                    "중기": analyzer.get_signal_text(res['w']), 
                    "장기": analyzer.get_signal_text(res['m'])
                })
                table_area.dataframe(pd.DataFrame(results), use_container_width=True)
            pbar.progress((i + 1) / len(target_list))
