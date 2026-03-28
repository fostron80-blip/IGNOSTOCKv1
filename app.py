import streamlit as st
import pandas as pd
import yfinance as yf
import FinanceDataReader as fdr
from datetime import datetime
import time

# --- [페이지 기본 설정] ---
st.set_page_config(page_title="ignostock v1.0 Web", layout="wide")

# --- [스타일 설정] ---
st.markdown("""
    <style>
    .main { background-color: #0F1115; }
    .stButton>button { width: 100%; border-radius: 5px; font-weight: bold; }
    div[data-testid="stExpander"] { border: none; }
    .status-box { padding: 10px; border-radius: 5px; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- [핵심 로직 클래스 (백엔드)] ---
class StockAnalyzer:
    def __init__(self):
        self.usd_krw = 1350.0
        self.sector_map = {
            "Technology": "기술", "Healthcare": "헬스케어", "Financial Services": "금융",
            "Consumer Cyclical": "경기소비재", "Industrials": "산업재", "Communication Services": "통신",
            "Consumer Defensive": "방어소비재", "Energy": "에너지", "Basic Materials": "기초소재",
            "Real Estate": "부동산", "Utilities": "유틸리티"
        }
        try:
            self.krx_listing = fdr.StockListing('KRX')[['Code', 'Sector']]
        except:
            self.krx_listing = pd.DataFrame(columns=['Code', 'Sector'])

    def get_ichimoku(self, df):
        if len(df) < 26: return 0, 0
        t = (df['High'].rolling(9).max() + df['Low'].rolling(9).min()) / 2
        k = (df['High'].rolling(26).max() + df['Low'].rolling(26).min()) / 2
        return t.iloc[-1], k.iloc[-1]

    def get_analysis(self, symbol, is_us):
        try:
            ticker_obj = yf.Ticker(symbol)
            info = ticker_obj.info
            raw_sector = info.get('sector', 'N/A')
            if raw_sector == 'N/A' and not is_us:
                pure_code = symbol.split('.')[0]
                matched = self.krx_listing[self.krx_listing['Code'] == pure_code]
                if not matched.empty: raw_sector = matched['Sector'].values[0]
            
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
                if target_df.empty or len(target_df) < 54: return {"t":0, "k":0, "c":0}
                t, k = self.get_ichimoku(target_df)
                c_s = target_df['Close']
                res = {"t": t, "k": k, "c": c_s.iloc[-1]}
                for p in [5, 9, 10, 15, 18, 20, 27, 36, 50, 54, 75]:
                    res[f"ma{p}"] = c_s.rolling(p).mean().iloc[-1] if len(target_df) >= p else 0
                return res

            d_data, w_data, m_data, s_data = calc_signals(df), calc_signals(w_df), calc_signals(m_df), calc_signals(s_df)
            st, col = "💤관망", "#161A1E"
            dt, dk, wt, wk, mt, mk = d_data['t'], d_data['k'], w_data['t'], w_data['k'], m_data['t'], m_data['k']
            
            # --- [롱/숏 조건 로직 - 원본과 동일하게 유지] ---
            if curr_p > dt and curr_p > dk and curr_p > wt and curr_p > wk and curr_p > mt and curr_p > mk and m_data['ma5'] > m_data['ma10'] > m_data['ma15'] > m_data['ma20']: st, col = "💎초강력 장기 롱", "#441A4D"
            elif curr_p > dt and curr_p > dk and curr_p > wt and curr_p > wk and curr_p > mt and curr_p > mk and w_data['ma5'] > w_data['ma10'] > w_data['ma15']: st, col = "💎초강력 장기 롱", "#441A4D"
            elif curr_p > dt and curr_p > dk and curr_p > wt and curr_p > wk and w_data['ma5'] > w_data['ma10'] > w_data['ma15']: st, col = "🔥강력 중기 롱", "#4D2A1A"
            elif curr_p > dt and curr_p > dk and curr_p > wt and d_data['ma5'] > d_data['ma10'] > d_data['ma15'] > d_data['ma20'] > d_data['ma50'] > d_data['ma75']: st, col = "🔥중기 롱", "#4D2A1A"
            elif curr_p > dt and curr_p > wt and curr_p > mt and w_data['ma5'] > w_data['ma10'] > w_data['ma15']: st, col = "🔥롱", "#4D1A1A"
            elif curr_p > mt and curr_p > mk and d_data['ma20'] < d_data['ma50'] < d_data['ma75'] and d_data['ma5'] > d_data['ma10'] > d_data['ma15']: st, col = "📈초강력 롱진입 상승초입", "#4D1A1A"
            elif curr_p > mt and d_data['ma20'] < d_data['ma50'] < d_data['ma75'] and d_data['ma5'] > d_data['ma10'] > d_data['ma15']: st, col = "📈롱진입 상승초입", "#4D1A1A"
            elif curr_p > wt and d_data['ma20'] < d_data['ma50'] < d_data['ma75'] and d_data['ma5'] > d_data['ma10'] > d_data['ma15']: st, col = "📈롱진입 상승초입", "#4D1A1A"
            elif curr_p > dt and d_data['ma20'] < d_data['ma50'] < d_data['ma75'] and d_data['ma5'] > d_data['ma10'] > d_data['ma15']: st, col = "📈롱진입 상승초입", "#4D1A1A"
            elif curr_p > dt and d_data['ma5'] < d_data['ma10'] < d_data['ma15'] and curr_p > d_data['ma5']: st, col = "📈롱진입중", "#4D1A1A"
            elif curr_p > dt and curr_p > dk and d_data['ma5'] > d_data['ma10'] > d_data['ma15']: st, col = "📈롱", "#4D1A1A"

            if curr_p < dt and curr_p < dk and curr_p < wt and curr_p < wk and curr_p < mt and curr_p < mk and d_data['ma5'] < d_data['ma10'] < d_data['ma15'] < d_data['ma20'] < d_data['ma50'] < d_data['ma75']: st, col = "💀초강력 장기 숏", "#1A2D2D"
            elif curr_p < dt and curr_p < dk and curr_p < wt and curr_p < wk and curr_p < mt and d_data['ma5'] < d_data['ma10'] < d_data['ma15'] < d_data['ma20'] < d_data['ma50'] < d_data['ma75']: st, col = "💀초강력 장기 숏", "#1A2D2D"
            elif curr_p < dt and curr_p < dk and curr_p < wt and curr_p < mt and d_data['ma5'] < d_data['ma10'] < d_data['ma15'] < d_data['ma20'] < d_data['ma50'] < d_data['ma75']: st, col = "💀강력 중기 숏", "#1A2D2D"
            elif curr_p < dt and curr_p < wt and curr_p < wk and d_data['ma5'] < d_data['ma10'] < d_data['ma15'] < d_data['ma20']: st, col = "📉숏 중기", "#1A1A4D"
            elif curr_p < dt and curr_p < wt and curr_p < wk and d_data['ma5'] < d_data['ma10'] < d_data['ma15'] < d_data['ma20']: st, col = "📉숏 중기진입", "#1A1A4D"
            elif curr_p < dt and curr_p < dk and d_data['ma5'] < d_data['ma10'] < d_data['ma15'] < d_data['ma20']: st, col = "📉강력숏", "#1A1A4D"
            elif curr_p < dt and d_data['ma20'] > d_data['ma50'] > d_data['ma75'] and curr_p < d_data['ma5'] and curr_p < d_data['ma10']: st, col = "📉숏진입", "#1A1A4D"
            elif curr_p < dt and d_data['ma20'] > d_data['ma50'] > d_data['ma75'] and curr_p < d_data['ma5']: st, col = "📉숏진입", "#1A1A4D"
            elif curr_p < dt and d_data['ma5'] < d_data['ma10'] < d_data['ma15']: st, col = "📉숏초입", "#1A1A4D"

            return {
                "curr": curr_p, "prev": float(df['Close'].iloc[-2]) if len(df)>1 else curr_p, 
                "low_52": float(df['Low'].tail(250).min()), "open_w": float(df.tail(datetime.now().weekday() + 1)['Open'].iloc[0]), 
                "marcap": marcap, "st": st, "col": col, "r3y": r3y, "r5y": r5y, "r10y": r10y, 
                "m": m_data, "w": w_data, "d": d_data, "s": s_data, "sector": sector_display
            }
        except: return None

    def get_signal_text(self, data):
        c, t, k = data.get('c', 0), data.get('t', 0), data.get('k', 0)
        m9, m18, m27 = data.get('ma9', 0), data.get('ma18', 0), data.get('ma27', 0)
        if t == 0: return "관망 😶🥱"
        if c < t and c < k and (m9 < m18 < m27) and (c < m9 and c < m18 and c < m27): return "🤬강력매도👎"
        if c > t and c > k and (m9 > m18 > m27) and (c > m9 and c > m18 and c > m27): return "😎강력매수👍"
        return "관망 😶🥱"

# --- [Streamlit UI] ---
st.title("🚀 ignostock v1.0 - Web Dashboard")

# 사이드바 설정
with st.sidebar:
    st.header("⚙️ 검색 설정")
    market_filter = st.selectbox("시장 선택", ["전체", "KOSPI", "KOSDAQ", "USA"])
    strategy_filter = st.selectbox("전략 필터", ["전체 검색", "💎 초강력 장기 롱", "🔥 강력 중기 롱", "📈 롱", "📉 중기 숏", "💀 초강력 장기 숏"])
    search_query = st.text_input("🔍 종목명/티커 검색", "")
    run_btn = st.button("스캔 시작", type="primary")

# 분석 시작
if run_btn:
    analyzer = StockAnalyzer()
    targets = []
    
    # 1. 대상 종목 수집
    with st.spinner("📡 대상 종목 리스트 생성 중..."):
        if search_query:
            df_krx = fdr.StockListing('KRX')
            df_filtered = df_krx[df_krx['Name'].str.lower().contains(search_query.lower()) | df_krx['Symbol'].str.lower().contains(search_query.lower())]
            for _, row in df_filtered.iterrows():
                suffix = ".KS" if row['Market'] == 'KOSPI' else ".KQ"
                targets.append([str(row['Symbol']) + suffix, row['Name'], row['Market']])
        else:
            if market_filter in ["전체", "KOSPI", "KOSDAQ"]:
                df_krx = fdr.StockListing('KRX').dropna(subset=['Marcap']).sort_values('Marcap', ascending=False).head(200) # 속도를 위해 상위 200개
                for _, row in df_krx.iterrows():
                    if market_filter != "전체" and row['Market'] != market_filter: continue
                    suffix = ".KS" if row['Market'] == 'KOSPI' else ".KQ"
                    targets.append([str(row['Symbol']) + suffix, row['Name'], row['Market']])
            if market_filter == "USA":
                df_us = fdr.StockListing('NASDAQ').head(100)
                for _, row in df_us.iterrows(): targets.append([row['Symbol'], row['Name'], "US"])

    # 2. 실시간 분석 및 표 업데이트
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    table_placeholder = st.empty()
    
    for i, (symbol, name, market) in enumerate(targets):
        status_text.text(f"분석 중: {name} ({i+1}/{len(targets)})")
        data = analyzer.get_analysis(symbol, (market == "US"))
        
        if data:
            # 전략 필터링
            if strategy_filter == "전체 검색" or data['st'] == strategy_filter:
                c = data['curr']
                day_chg = ((c/data['prev'])-1)*100
                w_chg = ((c/data['open_w'])-1)*100
                r52 = ((c/data['low_52'])-1)*100
                
                # 시가총액 포맷
                m_krw = (data['marcap'] * (1.0 if market != "US" else 1350.0)) / 1e12
                marcap_str = f"{m_krw:,.1f}조" if m_krw >= 1 else f"{m_krw*10000:,.0f}억"

                results.append({
                    "업종": data['sector'],
                    "티커": symbol,
                    "종목명": name,
                    "시가총액": marcap_str,
                    "현재가": f"{c:,.0f}" if market != "US" else f"${c:,.2f}",
                    "전일대비": f"{day_chg:+.2f}%",
                    "주간변동": f"{w_chg:+.2f}%",
                    "52주상승": f"{r52:,.1f}%",
                    "추세단계": data['st'],
                    "장기": analyzer.get_signal_text(data['m']),
                    "중기": analyzer.get_signal_text(data['w']),
                    "단기": analyzer.get_signal_text(data['d']),
                    "스윙": analyzer.get_signal_text(data['s'])
                })
                # 중간 결과 출력 (Streamlit 특성상 리스트를 데이터프레임으로 변환)
                table_placeholder.dataframe(pd.DataFrame(results), use_container_width=True)

        progress_bar.progress((i + 1) / len(targets))

    status_text.success(f"✅ 분석 완료! 총 {len(results)}개 종목 발견")
    
    # 엑셀 다운로드 기능
    if results:
        df_res = pd.DataFrame(results)
        csv = df_res.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 결과 엑셀(CSV) 다운로드", csv, "scan_result.csv", "text/csv")

else:
    st.info("왼쪽 사이드바에서 조건을 선택한 후 '스캔 시작' 버튼을 눌러주세요.")
