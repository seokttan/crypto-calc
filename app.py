import streamlit as st
import requests
import yfinance as yf
import pandas as pd
import time
from datetime import datetime, timedelta
from streamlit_cookies_controller import CookieController

# --- 쿠키 및 설정 ---
controller = CookieController()

# [1] 환율 데이터 (너무 자주 가져오면 차단되므로 캐싱 활용)
@st.cache_data(ttl=3600) # 1시간마다 환율 갱신
def get_exchange_rate():
    try:
        fx = yf.Ticker("USDKRW=X").history(period="1d")['Close'].iloc[-1]
        return fx
    except:
        return 1400.0

# [2] 코인 시세 데이터 (실시간 호출용)
def get_lbank_prices(coins):
    try:
        res = requests.get("https://api.lbkex.com/v2/ticker/24hr.do", params={'symbol': 'all'}, timeout=1).json()
        prices = {}
        if res.get('result') == 'true':
            lbank_map = {item['symbol'].replace('_usdt', '').upper(): float(item['ticker']['latest']) for item in res['data']}
            for coin in coins:
                prices[coin] = lbank_map.get(coin, 0.0)
        return prices
    except:
        return {coin: 0.0 for coin in coins}

# --- UI 설정 ---
st.set_page_config(page_title="Real-time Asset", layout="centered")

# 쿠키 로드
saved_coins = controller.get('my_target_coins')
if 'target_coins' not in st.session_state:
    st.session_state.target_coins = saved_coins if saved_coins else ['BTC', 'ETH', 'XRP', 'SOL', 'DOGE']

st.title("⚡ 실시간 자산 계산기")

# 입력창 영역 (루프 밖에 두어야 입력 중 초기화되지 않음)
col1, col2 = st.columns([1, 2])
with col1:
    base_asset = st.selectbox("기준 자산", ["KRW", "USDT"] + st.session_state.target_coins)
with col2:
    input_val = st.number_input("수량/금액 입력", min_value=0.0, value=1000000.0 if base_asset=="KRW" else 1.0)

# 실시간 업데이트를 위한 빈 공간 생성
placeholder = st.empty()

# 관리자 모드는 하단에 배치
with st.expander("⚙️ 자산 편집"):
    # (기존의 추가/삭제 코드와 동일)
    pass

# --- 🔄 실시간 무한 루프 시작 ---
while True:
    with placeholder.container():
        # 데이터 로드
        usd_to_krw = get_exchange_rate()
        coin_prices = get_lbank_prices(st.session_state.target_coins)
        
        # 한국 시간 계산
        kor_now = datetime.utcnow() + timedelta(hours=9)
        
        # 상단 환율 및 시간 표시
        st.caption(f"실시간 업데이트 중... (KST {kor_now.strftime('%H:%M:%S')})")
        st.metric("현재 환율", f"₩ {usd_to_krw:,.2f}")

        # 계산 로직
        if base_asset == "KRW":
            base_usdt = input_val / usd_to_krw
        elif base_asset == "USDT":
            base_usdt = input_val
        else:
            p_u = coin_prices.get(base_asset, 0.0)
            base_usdt = input_val * p_u if p_u > 0 else 0.0

        # 데이터 프레임 생성
        data = [
            ["KRW", "₩ 1.00", f"{base_usdt * usd_to_krw:,.0f}"],
            ["USDT", f"₩ {usd_to_krw:,.2f}", f"{base_usdt:,.2f}"]
        ]
        for coin in st.session_state.target_coins:
            p_u = coin_prices.get(coin, 0.0)
            qty = base_usdt / p_u if p_u > 0 else 0.0
            data.append([coin, f"₩ {p_u * usd_to_krw:,.2f}", f"{qty:,.6f}"])

        df = pd.DataFrame(data, columns=["자산", "시세(KRW)", "계산 수량"])
        
        # 테이블 출력 (인덱스 제거)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
    # 1초 대기 후 루프 재시작
    time.sleep(1)
