import streamlit as st 
import pandas as pd 
import yfinance as yf 
import FinanceDataReader as fdr 
from datetime import datetime 
import time 
  
# --- [1. 페이지 설정 및 CSS] --- 
st.set_config = st.set_page_config(page_title="ignostock v1.0", layout="wide") 
  
st.markdown(""" 
    <style> 
    .main { background-color: #0F1115; } 
    div.stButton > button { font-weight: bold; border-radius: 5px; height: 35px; width: 100%; } 
    .stProgress > div > div > div > div { background-color: #F0B90B; } 
    .stDataFrame { border: 1px solid #333; } 
    </style> 
    """, unsafe_allow_html=True) 
  
# --- [2. 핵심 분석 클래스 (원본 로직 100% 유지)] --- 
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
                if target_df.empty or len(target_df) < 54: return {"t":0, "k":0, "c":0} 
                t, k = self.get_ichimoku(target_df) 
                c_s = target_df['Close'] 
                res = {"t": t, "k": k, "c": c_s.iloc[-1]} 
                for p in [5, 9, 10, 15, 18, 20, 27, 36, 50, 54, 75]: 
                    res[f"ma{p}"] = c_s.rolling(p).mean().iloc[-1] if len(target_df) >= p else 0 
                return res 
            d_data, w_data, m_data, s_data = calc_signals(df), calc_signals(w_df), calc_signals(m_df), calc_signals(s_df) 
            st_text, col = "💤관망", "#161A1E" 
            dt, dk, wt, wk, mt, mk = d_data['t'], d_data['k'], w_data['t'], w_data['k'], m_data['t'], m_data['k'] 
            if curr_p > dt and curr_p > dk and curr_p > wt and curr_p > wk and curr_p > mt and curr_p > mk and m_data['ma5'] > m_data['ma10'] > m_data['ma15'] > m_data['ma20']: st_text, col = "💎초강력 장기 롱", "#441A4D" 
            elif curr_p > dt and curr_p > dk and curr_p > wt and curr_p > wk and curr_p > mt and curr_p > mk and w_data['ma5'] > w_data['ma10'] > w_data['ma15']: st_text, col = "💎초강력 장기 롱", "#441A4D" 
            elif curr_p > dt and curr_p > dk and curr_p > wt and curr_p > wk and w_data['ma5'] > w_data['ma10'] > w_data['ma15']: st_text, col = "🔥강력 중기 롱", "#4D2A1A" 
            elif curr_p > dt and curr_p > dk and curr_p > wt and d_data['ma5'] > d_data['ma10'] > d_data['ma15'] > d_data['ma20'] > d_data['ma50'] > d_data['ma75']: st_text, col = "🔥중기 롱", "#4D2A1A" 
            elif curr_p > dt and curr_p > wt and curr_p > mt and w_data['ma5'] > w_data['ma10'] > w_data['ma15']: st_text, col = "🔥롱", "#4D1A1A" 
            elif curr_p > mt and curr_p > mk and d_data['ma20'] < d_data['ma50'] < d_data['ma75'] and d_data['ma5'] > d_data['ma10'] > d_data['ma15']: st_text, col = "📈초강력 롱진입 상승초입", "#4D1A1A" 
            if curr_p < dt and curr_p < dk and curr_p < wt and curr_p < wk and curr_p < mt and curr_p < mk: st_text, col = "💀초강력 장기 숏", "#1A2D2D" 
            return { 
                "curr": curr_p, "prev": float(df['Close'].iloc[-2]) if len(df)>1 else curr_p,  
                "low_52": float(df['Low'].tail(250).min()),  
                "open_w": float(df.tail(datetime.now().weekday() + 1)['Open'].iloc[0]),  
                "marcap": marcap, "st": st_text, "col": col, "r3y": r3y, "r5y": r5y, "r10y": r10y,  
                "m": m_data, "w": w_data, "d": d_data, "s": s_data, "sector": sector_display 
            } 
        except: return None 
  
# --- [3. 메인 UI 및 검색 실행] --- 
analyzer = StockAnalyzer() 
st.sidebar.title("ignostock v1.0") 
m_choice = st.sidebar.radio("Market", ["KRX 전체", "KOSPI", "KOSDAQ", "USA"]) 
search_keyword = st.sidebar.text_input("🔍 종목명/티커 통합 검색").strip().lower() 

# 나래비 정렬 순서 정의
order_map = {
    "매수준비👍👍": 0, "😎매수👍": 1, "😎강력매수👍": 2, "강력상승기": 3, 
    "관망 😶🥱": 4, "매도관망👎": 5, "🤬매도👎": 6, "🤬지금당장매도👎👎": 7, "🤬강력매도👎👎👎": 8
}

if 'run' not in st.session_state: st.session_state.run = False
if 'sort_col' not in st.session_state: st.session_state.sort_col = None

btn_cols = st.columns(6)
if btn_cols[0].button("🚀 검색시작"): 
    st.session_state.run = True
    st.session_state.sort_col = None
if btn_cols[1].button("🛑 중지(초기화)"): 
    st.session_state.run = False
    st.rerun()

# 스윙, 단기, 중기, 장기 버튼 클릭 시 즉시 검색 및 해당 열 정렬 설정
for i, (label, col_name) in enumerate([("🌊 스윙", "스윙"), ("🕒 단기", "단기"), ("📅 중기", "중기"), ("📈 장기", "장기")]):
    if btn_cols[i+2].button(label):
        st.session_state.run = True
        st.session_state.sort_col = col_name

if st.session_state.run: 
    targets = [] 
    with st.spinner("📊 데이터베이스 동기화 중..."): 
        df_krx = fdr.StockListing('KRX').dropna(subset=['Marcap']) 
        c_key = 'Code' if 'Code' in df_krx.columns else 'Symbol' 
        if search_keyword: 
            df_f = df_krx[df_krx['Name'].str.lower().str.contains(search_keyword, na=False) | df_krx[c_key].str.lower().str.contains(search_keyword, na=False)] 
            for _, row in df_f.iterrows(): 
                targets.append([str(row[c_key]) + (".KS" if row['Market']=='KOSPI' else ".KQ"), row['Name'], row['Market']]) 
            try: 
                df_us = fdr.StockListing('NASDAQ') 
                u_key = 'Symbol' if 'Symbol' in df_us.columns else 'Code' 
                df_uf = df_us[df_us['Name'].str.lower().str.contains(search_keyword, na=False) | df_us[u_key].str.lower().str.contains(search_keyword, na=False)] 
                for _, row in df_uf.iterrows(): targets.append([str(row[u_key]), row['Name'], "US"]) 
            except: pass 
        else: 
            if m_choice == "USA": 
                df_us = fdr.StockListing('NASDAQ'); u_key = 'Symbol' if 'Symbol' in df_us.columns else 'Code'
                for _, row in df_us.iterrows(): targets.append([str(row[u_key]), row['Name'], "US"]) 
            else: 
                df_k = df_krx if m_choice == "KRX 전체" else df_krx[df_krx['Market'] == m_choice] 
                for _, row in df_k.iterrows(): targets.append([str(row[c_key]) + (".KS" if row['Market']=='KOSPI' else ".KQ"), row['Name'], row['Market']]) 
  
    results = [] 
    p_bar = st.progress(0); status = st.empty(); table_area = st.empty() 
     
    for i, (sym, name, mkt) in enumerate(targets): 
        if not st.session_state.run: break
        status.text(f"📡 [{i+1}/{len(targets)}] {name} 분석 중...") 
        res = analyzer.get_analysis(sym, (mkt == "US")) 
        if res: 
            m_krw = (res['marcap'] * (1.0 if mkt != "US" else 1350.0)) / 1e12 
            krw_str = f"{m_krw:,.1f}조" if m_krw >= 1 else f"{m_krw*10000:,.0f}억" 
            m_usd = (res['marcap'] / (1.0 if mkt == "US" else 1350.0)) 
            usd_str = f"${m_usd/1e12:,.2f}T" if m_usd >= 1e12 else (f"${m_usd/1e9:,.1f}B" if m_usd >= 1e9 else f"${m_usd/1e6:,.0f}M") 
            marcap_combined = f"{'🏢 ' if (m_usd >= 1e12 if mkt=='US' else m_krw >= 100) else '🏭 '}{usd_str} ({krw_str})" 
            r52 = ((res['curr']/res['low_52'])-1)*100 
            r_label = "🎇 과열진단" if r52 >= 300 else ("🚀 상승기" if r52 >= 50 else ("☘️ 바닥" if r52 >= 0 else "🚨 위험")) 

            results.append({ 
                "업종": res['sector'], "티커": sym.replace('.KS','').replace('.KQ',''), "종목명": f"{name}({mkt})", 
                "시가총액": marcap_combined, "현재가": f"${res['curr']:,.2f}" if mkt == "US" else f"{res['curr']:,.0f}원", 
                "전일대비": f"{((res['curr']/res['prev'])-1)*100:+.2f}%", "주간변동": f"{((res['curr']/res['open_w'])-1)*100:+.2f}%", 
                "과열진단": r_label, "추세단계": res['st'], 
                "스윙": analyzer.get_signal_text(res['s']), "단기": analyzer.get_signal_text(res['d']), 
                "중기": analyzer.get_signal_text(res['w']), "52주상승": f"{r52:,.1f}%", 
                "3년률": f"{res['r3y']:+.1f}%", "5년률": f"{res['r5y']:+.1f}%", "10년률": f"{res['r10y']:+.1f}%" 
            }) 
            
            # 실시간 나래비 정렬 적용
            final_df = pd.DataFrame(results)
            if st.session_state.sort_col:
                final_df['sort_key'] = final_df[st.session_state.sort_col].map(order_map).fillna(9)
                final_df = final_df.sort_values('sort_key').drop('sort_key', axis=1)
            
            table_area.dataframe(final_df, use_container_width=True, hide_index=True) 
        p_bar.progress((i+1)/len(targets)) 
    status.success(f"✅ 분석 완료 (총 {len(results)}개 종목)")
