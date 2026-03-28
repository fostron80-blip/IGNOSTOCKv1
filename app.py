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

# --- [2. 핵심 분석 클래스 (기본 로직 100% 유지)] ---
class StockAnalyzer:
    def __init__(self):
        self.usd_krw = 1350.0
        self.sector_map = {
            "Technology": "기술", "Healthcare": "헬스케어", "Financial Services": "금융",
            "Consumer Cyclical": "경기소비재", "Industrials": "산업재", "Communication Services": "통신",
            "Consumer Defensive": "방어소비재", "Energy": "에너지", "Basic Materials": "기초소재",
            "Real Estate": "부동산", "Utilities": "유틸리티"
        }
        self.krx_listing = self.get_safe_listing('KRX')

    def get_safe_listing(self, market):
        # 데이터 로드 실패 시 빈 데이터프레임 반환하여 크래시 방지
        try:
            return fdr.StockListing(market)
        except:
            return pd.DataFrame()

    def get_ichimoku(self, df):
        if len(df) < 26: return 0, 0
        t = (df['High'].rolling(9).max() + df['Low'].rolling(9).min()) / 2
        k = (df['High'].rolling(26).max() + df['Low'].rolling(26).min()) / 2
        return t.iloc[-1], k.iloc[-1]

    def get_signal_text(self, data):
        c, t, k = data.get('c', 0), data.get('t', 0), data.get('k', 0)
        m9, m18, m27, m36, m54 = data.get('ma9', 0), data.get('ma18', 0), data.get('ma27', 0), data.get('ma36', 0), data.get('ma54', 0)
        if t == 0: return "관망 😶🥱"
        if c < t and c < k and (m9 < m18 < m27) and (c < m9 and c < m18 and c < m27): return "🤬강력매도👎👎👎"
        if c < t and c < k and (c < m9 and c < m18 and c < m27): return "🤬강력매도👎👎👎"
        if (m9 > m18 > m27) and c < m9: return "🤬지금당장매도👎👎"
        if c < k and c > t and (m9 < m18 < m27): return "🤬매도👎"
        if c < t and (c < m9 and c < m18): return "🤬매도👎"
        if c < m36 and c < m54 and c > k and c > m9: return "매도관망👎"
        if c > t and c > k and (m9 > m18 > m27) and (c > m9 and c > m18 and c > m27): return "강력상승기"
        if c > t and c > k and (c > m9 and c > m18 and c > m27): return "😎강력매수👍"
        if c > t and c > k and c > m9: return "😎매수👍"
        if c > m36 and c > m54 and c > k and (m9 > m18 > m27) and (c > m9 and c > m18 and c > m27): return "😎매수👍"
        if c > t and (c > m9 and c > m18): return "매수준비👍👍"
        if c > m36 and c > m54 and c > k and c > m9: return "매수준비👍"
        if (m9 > m18 > m27): return "매수"
        return "관망 😶🥱"

    def get_analysis(self, symbol, is_us):
        try:
            ticker_obj = yf.Ticker(symbol)
            info = ticker_obj.info
            raw_sector = info.get('sector', 'N/A')
            if raw_sector == 'N/A' and not is_us:
                pure_code = symbol.split('.')[0]
                if not self.krx_listing.empty:
                    # 'Code' 또는 'Symbol' 열 대응
                    c_col = 'Code' if 'Code' in self.krx_listing.columns else 'Symbol'
                    matched = self.krx_listing[self.krx_listing[c_col] == pure_code]
                    if not matched.empty: 
                        raw_sector = matched['Sector'].values[0] if 'Sector' in matched.columns else 'N/A'
            
            kr_sector = self.sector_map.get(raw_sector, raw_sector)
            sector_display = f"{kr_sector}({raw_sector})" if raw_sector != 'N/A' else "N/A"
            
            df_hour = ticker_obj.history(period="60d", interval="1h")
            df = ticker_obj.history(period="10y", interval="1d")
            if df.empty or len(df) < 10: return None
            
            m_df = df.resample('ME').last() 
            w_df = df.resample('W-MON').last() 
            s_df = df_hour.resample('2h').last().dropna()
            curr_p = float(df['Close'].iloc[-1])
            marcap = info.get('marketCap', 0)

            def get_period_return(months):
                if len(m_df) < months: return 0.0
                period_min = m_df['Low'].tail(months).min()
                return ((curr_p / period_min) - 1) * 100 if period_min > 0 else 0.0

            r3y, r5y, r10y = get_period_return(36), get_period_return(60), get_period_return(120)

            def calc_signals(target_df):
                if target_df.empty or len(target_df) < 54: 
                    return {"t":0, "k":0, "ma5":0, "ma9":0, "ma10":0, "ma15":0, "ma18":0, "ma20":0, "ma27":0, "ma36":0, "ma54":0, "c":0}
                t, k = self.get_ichimoku(target_df)
                c_s = target_df['Close']
                res = {"t": t, "k": k, "c": c_s.iloc[-1]}
                for p in [5, 9, 10, 15, 18, 20, 27, 36, 50, 54, 75]:
                    res[f"ma{p}"] = c_s.rolling(p).mean().iloc[-1] if len(target_df) >= p else 0
                return res

            d_data, w_data, m_data, s_data = calc_signals(df), calc_signals(w_df), calc_signals(m_df), calc_signals(s_df)
            st_text, col = "💤관망", "#161A1E"
            dt, dk, wt, wk, mt, mk = d_data['t'], d_data['k'], w_data['t'], w_data['k'], m_data['t'], m_data['k']
            
            # --- 추세 로직 그대로 ---
            if curr_p > dt and curr_p > dk and curr_p > wt and curr_p > wk and curr_p > mt and curr_p > mk and m_data['ma5'] > m_data['ma10'] > m_data['ma15'] > m_data['ma20']: st_text, col = "💎초강력 장기 롱", "#441A4D"
            elif curr_p > dt and curr_p > dk and curr_p > wt and curr_p > wk and curr_p > mt and curr_p > mk and w_data['ma5'] > w_data['ma10'] > w_data['ma15']: st_text, col = "💎초강력 장기 롱", "#441A4D"
            elif curr_p > dt and curr_p > dk and curr_p > wt and curr_p > wk and w_data['ma5'] > w_data['ma10'] > w_data['ma15']: st_text, col = "🔥강력 중기 롱", "#4D2A1A"
            elif curr_p > dt and curr_p > dk and curr_p > wt and d_data['ma5'] > d_data['ma10'] > d_data['ma15'] > d_data['ma20'] > d_data['ma50'] > d_data['ma75']: st_text, col = "🔥중기 롱", "#4D2A1A"
            elif curr_p > dt and curr_p > wt and curr_p > mt and w_data['ma5'] > w_data['ma10'] > w_data['ma15']: st_text, col = "🔥롱", "#4D1A1A"
            elif curr_p > mt and curr_p > mk and d_data['ma20'] < d_data['ma50'] < d_data['ma75'] and d_data['ma5'] > d_data['ma10'] > d_data['ma15']: st_text, col = "📈초강력 롱진입 상승초입", "#4D1A1A"
            elif curr_p > mt and d_data['ma20'] < d_data['ma50'] < d_data['ma75'] and d_data['ma5'] > d_data['ma10'] > d_data['ma15']: st_text, col = "📈롱진입 상승초입", "#4D1A1A"
            elif curr_p > wt and d_data['ma20'] < d_data['ma50'] < d_data['ma75'] and d_data['ma5'] > d_data['ma10'] > d_data['ma15']: st_text, col = "📈롱진입 상승초입", "#4D1A1A"
            elif curr_p > dt and d_data['ma20'] < d_data['ma50'] < d_data['ma75'] and d_data['ma5'] > d_data['ma10'] > d_data['ma15']: st_text, col = "📈롱진입 상승초입", "#4D1A1A"
            elif curr_p > dt and d_data['ma5'] < d_data['ma10'] < d_data['ma15'] and curr_p > d_data['ma5']: st_text, col = "📈롱진입중", "#4D1A1A"
            elif curr_p > dt and curr_p > dk and d_data['ma5'] > d_data['ma10'] > d_data['ma15']: st_text, col = "📈롱", "#4D1A1A"

            if curr_p < dt and curr_p < dk and curr_p < wt and curr_p < wk and curr_p < mt and curr_p < mk and d_data['ma5'] < d_data['ma10'] < d_data['ma15'] < d_data['ma20'] < d_data['ma50'] < d_data['ma75']: st_text, col = "💀초강력 장기 숏", "#1A2D2D"
            elif curr_p < dt and curr_p < dk and curr_p < wt and curr_p < wk and curr_p < mt and d_data['ma5'] < d_data['ma10'] < d_data['ma15'] < d_data['ma20'] < d_data['ma50'] < d_data['ma75']: st_text, col = "💀초강력 장기 숏", "#1A2D2D"
            elif curr_p < dt and curr_p < dk and curr_p < wt and curr_p < mt and d_data['ma5'] < d_data['ma10'] < d_data['ma15'] < d_data['ma20'] < d_data['ma50'] < d_data['ma75']: st_text, col = "💀강력 중기 숏", "#1A2D2D"
            elif curr_p < dt and curr_p < wt and curr_p < wk and d_data['ma5'] < d_data['ma10'] < d_data['ma15'] < d_data['ma20']: st_text, col = "📉숏 중기", "#1A1A4D"
            elif curr_p < dt and curr_p < wt and curr_p < wk and d_data['ma5'] < d_data['ma10'] < d_data['ma15'] < d_data['ma20']: st_text, col = "📉숏 중기진입", "#1A1A4D"
            elif curr_p < dt and curr_p < dk and d_data['ma5'] < d_data['ma10'] < d_data['ma15'] < d_data['ma20']: st_text, col = "📉강력숏", "#1A1A4D"
            elif curr_p < dt and d_data['ma20'] > d_data['ma50'] > d_data['ma75'] and curr_p < d_data['ma5'] and curr_p < d_data['ma10']: st_text, col = "📉숏진입", "#1A1A4D"
            elif curr_p < dt and d_data['ma20'] > d_data['ma50'] > d_data['ma75'] and curr_p < d_data['ma5']: st_text, col = "📉숏진입", "#1A1A4D"
            elif curr_p < dt and d_data['ma5'] < d_data['ma10'] < d_data['ma15']: st_text, col = "📉숏초입", "#1A1A4D"

            return {
                "curr": curr_p, "prev": float(df['Close'].iloc[-2]) if len(df)>1 else curr_p, 
                "low_52": float(df['Low'].tail(250).min()), 
                "open_w": float(df.tail(datetime.now().weekday() + 1)['Open'].iloc[0]), 
                "marcap": marcap, "st": st_text, "col": col, "r3y": r3y, "r5y": r5y, "r10y": r10y, 
                "m": m_data, "w": w_data, "d": d_data, "s": s_data, "sector": sector_display
            }
        except: return None

# --- [3. 메인 UI] ---
analyzer = StockAnalyzer()

st.sidebar.title("ignostock v1.0")
m_choice = st.sidebar.radio("Market", ["KRX 전체", "KOSPI", "KOSDAQ", "USA"])
search_keyword = st.sidebar.text_input("🔍 종목명/티커 검색").strip().lower()

if 'trend_mode' not in st.session_state: st.session_state.trend_mode = "전체 검색"
filters = ["전체 검색", "💎 초강력 장기 롱", "🔥 강력 중기 롱", "📈 롱", "📉 중기 숏", "💀 초강력 장기 숏"]
t_cols = st.columns(len(filters))
for i, f in enumerate(filters):
    if t_cols[i].button(f): st.session_state.trend_mode = f

if st.button("🚀 스캔 시작"):
    targets = []
    with st.spinner("📦 리스트 준비 중..."):
        try:
            # 시장별 리스팅
            if "USA" in m_choice:
                df_raw = fdr.StockListing('NASDAQ')
                c_key = 'Symbol' if 'Symbol' in df_raw.columns else 'Code'
            else:
                df_raw = fdr.StockListing('KRX')
                c_key = 'Code' if 'Code' in df_raw.columns else 'Symbol'
            
            # 필터링
            if search_keyword:
                df_raw = df_raw[df_raw['Name'].str.lower().str.contains(search_keyword, na=False) | 
                                df_raw[c_key].str.lower().str.contains(search_keyword, na=False)]
            elif "KOSPI" in m_choice:
                df_raw = df_raw[df_raw['Market'] == 'KOSPI']
            elif "KOSDAQ" in m_choice:
                df_raw = df_raw[df_raw['Market'] == 'KOSDAQ']

            for _, row in df_raw.iterrows():
                sym = str(row[c_key])
                if "USA" not in m_choice:
                    sym += ".KS" if row.get('Market') == 'KOSPI' else ".KQ"
                targets.append([sym, row['Name'], row.get('Market', 'US')])
        except Exception as e:
            st.error(f"목록 로드 실패: {e}")

    results = []
    pbar = st.progress(0)
    table_area = st.empty()
    
    for i, (sym, name, mkt) in enumerate(targets):
        res = analyzer.get_analysis(sym, (mkt == "US"))
        if res:
            if st.session_state.trend_mode == "전체 검색" or st.session_state.trend_mode in res['st']:
                # 결과 정리 (기존 포맷 유지)
                m_krw = (res['marcap'] * (1350.0 if mkt == "US" else 1.0)) / 1e12
                marcap_str = f"{m_krw:,.1f}조" if m_krw >= 1 else f"{m_krw*10000:,.0f}억"
                
                results.append({
                    "티커": sym.split('.')[0], "종목명": name, "시가총액": marcap_str,
                    "현재가": f"{res['curr']:,.0f}", "추세": res['st'],
                    "단기": analyzer.get_signal_text(res['d']), "중기": analyzer.get_signal_text(res['w']), "장기": analyzer.get_signal_text(res['m'])
                })
                table_area.dataframe(pd.DataFrame(results), use_container_width=True)
        pbar.progress((i+1)/len(targets))
