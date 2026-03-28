import streamlit as st
import pandas as pd
import yfinance as yf
import FinanceDataReader as fdr
from datetime import datetime
import time

# --- [1. 페이지 설정] ---
st.set_page_config(page_title="ignostock v1.0 FULL-SCAN", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0F1115; }
    div.stButton > button:first-child {
        background-color: #F0B90B; color: black; font-weight: bold; width: 100%;
    }
    </style>
    """, unsafe_allow_html=True)

# --- [2. 분석 클래스] ---
class StockAnalyzer:
    def __init__(self):
        self.usd_krw = 1350.0
        try:
            # 시작할 때 한 번만 로드하여 속도 향상
            self.krx_listing = fdr.StockListing('KRX')
        except:
            self.krx_listing = pd.DataFrame()

    def get_ichimoku(self, df):
        if len(df) < 26: return 0, 0
        t = (df['High'].rolling(9).max() + df['Low'].rolling(9).min()) / 2
        k = (df['High'].rolling(26).max() + df['Low'].rolling(26).min()) / 2
        return t.iloc[-1], k.iloc[-1]

    def get_analysis(self, symbol, is_us):
        try:
            ticker_obj = yf.Ticker(symbol)
            # 서버 부하를 줄이기 위해 info 대신 history 데이터 위주로 사용
            df = ticker_obj.history(period="10y", interval="1d")
            if df.empty or len(df) < 60: return None
            
            df_hour = ticker_obj.history(period="30d", interval="1h")
            
            # 리샘플링
            m_df = df.resample('ME').last() 
            w_df = df.resample('W-MON').last() 
            s_df = df_hour.resample('2h').last().dropna()
            
            curr_p = float(df['Close'].iloc[-1])
            prev_p = float(df['Close'].iloc[-2]) if len(df) > 1 else curr_p

            # 지표 계산 함수
            def calc_signals(target_df):
                if target_df.empty or len(target_df) < 54: 
                    return {"t":0, "k":0, "c":0}
                t, k = self.get_ichimoku(target_df)
                c_s = target_df['Close']
                res = {"t": t, "k": k, "c": c_s.iloc[-1]}
                for p in [5, 9, 10, 15, 18, 20, 27, 36, 50, 54, 75]:
                    res[f"ma{p}"] = c_s.rolling(p).mean().iloc[-1] if len(target_df) >= p else 0
                return res

            d_data, w_data, m_data, s_data = calc_signals(df), calc_signals(w_df), calc_signals(m_df), calc_signals(s_df)
            st_text, col = "💤관망", "#161A1E"
            dt, dk, wt, wk, mt, mk = d_data['t'], d_data['k'], w_data['t'], w_data['k'], m_data['t'], m_data['k']
            
            # 롱/숏 조건 (사용자 요청 로직 유지)
            if curr_p > dt and curr_p > dk and curr_p > wt and curr_p > wk and curr_p > mt and curr_p > mk:
                if d_data.get('ma5', 0) > d_data.get('ma10', 0) > d_data.get('ma15', 0): st_text, col = "🔥강력 롱", "#4D2A1A"
            elif curr_p < dt and curr_p < dk and curr_p < wt:
                if d_data.get('ma5', 0) < d_data.get('ma10', 0): st_text, col = "📉숏", "#1A1A4D"

            return {
                "curr": curr_p, "prev": prev_p, "st": st_text, "col": col,
                "d": d_data, "w": w_data, "m": m_data, "s": s_data,
                "low_52": float(df['Low'].tail(250).min()),
                "open_w": float(df.tail(datetime.now().weekday() + 1)['Open'].iloc[0])
            }
        except: return None

# --- [3. 메인 화면] ---
st.sidebar.header("🔍 전체 종목 스캔 설정")
market_choice = st.sidebar.selectbox("대상 시장", ["KRX 전체", "KOSPI", "KOSDAQ", "USA"])
limit_val = st.sidebar.number_input("스캔 개수 (전체는 약 2600)", value=3000)
start_btn = st.sidebar.button("전체 스캔 시작 (상당히 오래 걸림)")

if start_btn:
    analyzer = StockAnalyzer()
    targets = []
    
    with st.spinner("📦 종목 리스트 불러오는 중..."):
        df_krx = analyzer.krx_listing
        code_col = 'Code' if 'Code' in df_krx.columns else 'Symbol'
        
        if market_choice == "KRX 전체":
            df_target = df_krx
        elif market_choice in ["KOSPI", "KOSDAQ"]:
            df_target = df_krx[df_krx['Market'] == market_choice]
        else: # USA
            df_target = fdr.StockListing('NASDAQ')
            code_col = 'Symbol'

        df_target = df_target.head(limit_val)
        for _, row in df_target.iterrows():
            sym = str(row[code_col])
            if market_choice != "USA":
                sym += ".KS" if row.get('Market') == 'KOSPI' else ".KQ"
            targets.append([sym, row['Name']])

    results = []
    prog = st.progress(0)
    status = st.empty()
    table = st.empty()

    for i, (sym, name) in enumerate(targets):
        status.text(f"⏳ 분석 중 ({i+1}/{len(targets)}): {name}")
        res = analyzer.get_analysis(sym, (market_choice == "USA"))
        
        if res:
            # 💤관망 종목은 빼고 결과에 추가 (표가 너무 길어지는 것 방지)
            if res['st'] != "💤관망":
                day_chg = ((res['curr']/res['prev'])-1)*100
                results.append({
                    "티커": sym.split('.')[0],
                    "종목명": name,
                    "현재가": f"{res['curr']:.0f}",
                    "등락": f"{day_chg:+.2f}%",
                    "추세": res['st'],
                    "52주저점대비": f"{((res['curr']/res['low_52'])-1)*100:.1f}%"
                })
                table.dataframe(pd.DataFrame(results), use_container_width=True)
        
        prog.progress((i + 1) / len(targets))
        # 서버 끊김 방지를 위해 아주 잠깐 쉬어줌
        if i % 10 == 0: time.sleep(0.01)

    status.success(f"✅ 스캔 완료! ({len(results)}개 종목 발견)")
else:
    st.warning("⚠️ '전체 스캔'은 종목이 많아 10~20분 이상 소요될 수 있습니다. 브라우저 창을 닫지 마세요.")
