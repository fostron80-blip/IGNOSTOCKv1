import streamlit as st
import pandas as pd
import yfinance as yf
import FinanceDataReader as fdr
from datetime import datetime
import time

# --- [1. 페이지 설정 및 CSS] ---
st.set_page_config(page_title="ignostock v1.0", layout="wide")

# 기존 UI의 어두운 테마와 버튼 색상을 최대한 재현
st.markdown("""
    <style>
    .main { background-color: #0F1115; }
    div.stButton > button {
        font-weight: bold; border-radius: 5px; height: 35px; width: 100%;
    }
    .stProgress > div > div > div > div { background-color: #F0B90B; }
    /* 테이블 가독성을 위한 스타일 */
    .reportview-container .main .block-container { padding-top: 1rem; }
    </style>
    """, unsafe_allow_html=True)

# --- [2. 핵심 분석 클래스 (기존 로직 복사)] ---
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
                if target_df.empty or len(target_df) < 54: 
                    return {"t":0, "k":0, "ma5":0, "ma9":0, "ma10":0, "ma15":0, "ma18":0, "ma20":0, "ma27":0, "ma36":0, "ma54":0, "c":0}
                t, k = self.get_ichimoku(target_df)
                c_s = target_df['Close']
                res = {"t": t, "k": k, "c": c_s.iloc[-1]}
                for p in [5, 9, 10, 15, 18, 20, 27, 36, 50, 54, 75]:
                    res[f"ma{p}"] = c_s.rolling(p).mean().iloc[-1] if len(target_df) >= p else 0
                return res

            d_data, w_data, m_data, s_data = calc_signals(df), calc_signals(w_df), calc_signals(m_df), calc_signals(s_df)
            st, col = "💤관망", "#161A1E"
            dt, dk, wt, wk, mt, mk = d_data['t'], d_data['k'], w_data['t'], w_data['k'], m_data['t'], m_data['k']
            
            # --- 추세 로직 그대로 복사 ---
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
                "low_52": float(df['Low'].tail(250).min()), 
                "open_w": float(df.tail(datetime.now().weekday() + 1)['Open'].iloc[0]), 
                "marcap": marcap, "st": st, "col": col, "r3y": r3y, "r5y": r5y, "r10y": r10y, 
                "m": m_data, "w": w_data, "d": d_data, "s": s_data, "sector": sector_display
            }
        except: return None

# --- [3. UI 레이아웃 및 제어 로직] ---
analyzer = StockAnalyzer()

# 사이드바 설정 (시장 선택 및 검색)
st.sidebar.title("ignostock v1.0")
m_choice = st.sidebar.radio("Market Selection", ["KOSPI", "KOSDAQ", "USA", "KRX 전체"], index=3)
search_keyword = st.sidebar.text_input("🔍 종목명/티커 통합 검색", "").strip().lower()

# 추세 필터 버튼 (Session State를 이용해 PyQt 버튼 동작 재현)
if 'trend_mode' not in st.session_state: st.session_state.trend_mode = "전체 검색"
filters = ["전체 검색", "💎 초강력 장기 롱", "🔥 강력 중기 롱", "📈 롱", "📉 중기 숏", "💀 초강력 장기 숏"]
cols = st.columns(len(filters))
for i, f in enumerate(filters):
    if cols[i].button(f): st.session_state.trend_mode = f

# 분석 시작 버튼
if st.button("🚀 전체 분석 및 스캔 시작"):
    targets = []
    with st.spinner("📡 데이터베이스 동기화 중..."):
        # 검색 필터 로직 그대로 적용
        if search_keyword:
            df_krx = fdr.StockListing('KRX').dropna(subset=['Marcap'])
            code_col = 'Code' if 'Code' in df_krx.columns else 'Symbol'
            df_filtered = df_krx[df_krx['Name'].str.lower().str.contains(search_keyword, na=False) | 
                                 df_krx[code_col].str.lower().str.contains(search_keyword, na=False)]
            for _, row in df_filtered.iterrows():
                suffix = ".KS" if row['Market'] == 'KOSPI' else ".KQ"
                targets.append([str(row[code_col]) + suffix, row['Name'], row['Market']])
            
            try:
                df_us = fdr.StockListing('NASDAQ')
                us_code = 'Symbol' if 'Symbol' in df_us.columns else 'Code'
                df_us_f = df_us[df_us['Name'].str.lower().str.contains(search_keyword, na=False) | 
                                df_us[us_code].str.lower().str.contains(search_keyword, na=False)]
                for _, row in df_us_f.iterrows(): targets.append([str(row[us_code]), row['Name'], "US"])
            except: pass
        else:
            if m_choice == "USA":
                df_us = fdr.StockListing('NASDAQ')
                code_col = 'Symbol' if 'Symbol' in df_us.columns else 'Code'
                for _, row in df_us.iterrows(): targets.append([str(row[code_col]), row['Name'], "US"])
            else:
                df_krx = fdr.StockListing('KRX').dropna(subset=['Marcap'])
                if m_choice == "KOSPI": df_krx = df_krx[df_krx['Market'] == 'KOSPI']
                elif m_choice == "KOSDAQ": df_krx = df_krx[df_krx['Market'] == 'KOSDAQ']
                code_col = 'Code' if 'Code' in df_krx.columns else 'Symbol'
                for _, row in df_krx.iterrows():
                    suffix = ".KS" if row['Market'] == 'KOSPI' else ".KQ"
                    targets.append([str(row[code_col]) + suffix, row['Name'], row['Market']])

    # 결과 분석 루프
    results = []
    prog_bar = st.progress(0)
    status_txt = st.empty()
    table_placeholder = st.empty()
    
    total = len(targets)
    for i, (symbol, name, market) in enumerate(targets):
        status_txt.text(f"📡 [{i+1}/{total}] {name} 분석 중...")
        data = analyzer.get_analysis(symbol, (market == "US"))
        
        if data:
            c, st_val = data['curr'], data['st']
            day_chg = ((c/data['prev'])-1)*100
            w_chg = ((c/data['open_w'])-1)*100
            r52 = ((c/data['low_52'])-1)*100
            
            # 시가총액 계산 로직 그대로
            m_krw = (data['marcap'] * (1.0 if market != "US" else 1350.0)) / 1e12
            krw_str = f"{m_krw:,.1f}조" if m_krw >= 1 else f"{m_krw*10000:,.0f}억"
            m_usd = (data['marcap'] / (1.0 if market == "US" else 1350.0))
            usd_str = f"${m_usd/1e12:,.2f}T" if m_usd >= 1e12 else (f"${m_usd/1e9:,.1f}B" if m_usd >= 1e9 else f"${m_usd/1e6:,.0f}M")
            is_giant = (m_usd >= 1e12) if market == "US" else (m_krw >= 100)
            marcap_display = f"{'🏢 ' if is_giant else '🏭 '}{usd_str} ({krw_str})"

            # 과열 진단 라벨 그대로
            r_label = "🎇 과열진단" if r52 >= 300 else ("🚀 상승기" if r52 >= 50 else ("☘️ 바닥" if r52 >= 0 else "🚨 위험"))

            # 필터링 및 리스트 추가
            if st.session_state.trend_mode == "전체 검색" or st.session_state.trend_mode in st_val:
                results.append({
                    "업종": data['sector'], "티커": symbol.replace('.KS','').replace('.KQ',''),
                    "종목명": f"{name}({market})", "시가총액": marcap_display,
                    "현재가": f"${c:,.2f}" if market=="US" else f"{c:,.0f}원",
                    "전일대비": f"{day_chg:+.2f}%", "주간변동": f"{w_chg:+.2f}%",
                    "3년률": f"{data['r3y']:+.1f}%", "5년률": f"{data['r5y']:+.1f}%", "10년률": f"{data['r10y']:+.1f}%",
                    "52주상승": f"{r52:,.1f}%", "과열진단": r_label, "추세단계": st_val,
                    "스윙": analyzer.get_signal_text(data['s']), "단기": analyzer.get_signal_text(data['d']),
                    "중기": analyzer.get_signal_text(data['w']), "장기": analyzer.get_signal_text(data['m'])
                })
                # 실시간으로 테이블 업데이트
                table_placeholder.dataframe(pd.DataFrame(results), use_container_width=True)
        
        prog_bar.progress((i+1)/total)
    
    status_txt.success(f"✅ 분석 완료 (총 {len(results)}개 종목 발견)")
    
    # 엑셀 저장 버튼
    if results:
        df_res = pd.DataFrame(results)
        csv = df_res.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 결과 엑셀(CSV) 저장", csv, f"scan_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
else:
    st.info("좌측 설정을 확인하고 '분석 시작' 버튼을 눌러주세요. 전체 종목 분석은 수십 분이 소요될 수 있습니다.")
