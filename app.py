import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from streamlit_cookies_controller import CookieController
from curl_cffi import requests as requests_cffi

# --- [1] 설정 및 쿠키 초기화 ---
controller = CookieController()

@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        # Yahoo Finance API 직접 호출 (curl_cffi 우회)
        url = "https://query1.finance.yahoo.com/v8/finance/chart/USDKRW=X?interval=1m&range=1d"
        r = requests_cffi.Session(impersonate="chrome").get(url, timeout=5)
        data = r.json()
        price = data['chart']['result'][0]['meta']['regularMarketPrice']
        return float(price)
    except:
        return 1425.0  # 실패 시 최근 근사치

def get_lbank_prices(coins):
    try:
        res = requests.get("https://api.lbkex.com/v2/ticker/24hr.do", params={'symbol': 'all'}, timeout=2).json()
        if res.get('result') == 'true':
            lbank_map = {item['symbol'].replace('_usdt', '').upper(): float(item['ticker']['latest']) for item in res['data']}
            return {coin: lbank_map.get(coin, 0.0) for coin in coins}
        return {coin: 0.0 for coin in coins}
    except:
        return {coin: 0.0 for coin in coins}

# --- [2] UI 레이아웃 설정 ---
st.set_page_config(page_title="Asset Intelligence", layout="centered")

# 쿠키 로드 (세션에 보관)
if 'target_coins' not in st.session_state:
    saved_coins = controller.get('my_target_coins')
    st.session_state.target_coins = saved_coins if saved_coins else ['BTC', 'ETH', 'XRP', 'SOL', 'DOGE']

# 상단 타이틀 (문구 삭제 및 심플하게 유지)

# --- [3] 계산 기준 설정 (상단 고정) ---
with st.container():
    c1, c2 = st.columns([1, 2])
    with c1:
        base_asset = st.selectbox("기준 자산", ["KRW", "USDT"] + st.session_state.target_coins)
    with c2:
        default_val = 1000000.0 if base_asset == "KRW" else 1.0
        input_val = st.number_input("수량/금액 입력", min_value=0.0, value=default_val, step=1.0)

st.divider()

# --- [4] 실시간 결과 출력 영역 (중앙) ---
placeholder = st.empty()

# --- [5] 자산 리스트 편집 (최하단 배치를 위해 루프 밖 하단에 작성해야 함) ---
# 하지만 실시간 루프(while True)가 실행되면 아래 코드로 내려가지 않으므로, 
# 편집창을 '사이드바'에 넣거나, 루프 내부 placeholder 아래에 배치하는 것이 표준입니다.
# 요청하신 대로 '맨 밑'에 두기 위해 루프 구조를 조정했습니다.

def render_editor():
    with st.expander("⚙️ 내 자산 리스트 편집 (쿠키 저장)"):
        add_col, del_col = st.columns(2)
        with add_col:
            new_coin = st.text_input("추가할 코인 심볼 (예: SOL)").upper().strip()
            if st.button("추가"):
                if new_coin and new_coin not in st.session_state.target_coins:
                    st.session_state.target_coins.append(new_coin)
                    controller.set('my_target_coins', st.session_state.target_coins, max_age=31536000)
                    st.success(f"{new_coin} 추가됨")
                    time.sleep(0.5)
                    st.rerun()
        with del_col:
            if st.session_state.target_coins:
                del_coin = st.selectbox("삭제할 코인 선택", st.session_state.target_coins)
                if st.button("삭제"):
                    st.session_state.target_coins.remove(del_coin)
                    controller.set('my_target_coins', st.session_state.target_coins, max_age=31536000)
                    st.warning(f"{del_coin} 삭제됨")
                    time.sleep(0.5)
                    st.rerun()

# --- [6] 실시간 루프 및 편집창 배치 ---
# 무한 루프 대신 st.empty를 활용하여 편집창을 루프 아래에 물리적으로 고정합니다.
while True:
    with placeholder.container():
        usd_to_krw = get_exchange_rate()
        coin_prices = get_lbank_prices(st.session_state.target_coins)
        kor_now = datetime.utcnow() + timedelta(hours=9)
        
        # 정보 표시
        st.caption(f"KST {kor_now.strftime('%H:%M:%S')} | 환율 ₩ {usd_to_krw:,.2f}")

        # 계산 로직
        if base_asset == "KRW":
            base_usdt = input_val / usd_to_krw
        elif base_asset == "USDT":
            base_usdt = input_val
        else:
            p_u = coin_prices.get(base_asset, 0.0)
            base_usdt = input_val * p_u if p_u > 0 else 0.0

        # 데이터 테이블 생성
        data = [
            ["KRW", "₩ 1.00", f"{base_usdt * usd_to_krw:,.0f}"],
            ["USDT", f"₩ {usd_to_krw:,.2f}", f"{base_usdt:,.2f}"]
        ]
        
        for coin in st.session_state.target_coins:
            p_u = coin_prices.get(coin, 0.0)
            p_k = p_u * usd_to_krw
            qty = base_usdt / p_u if p_u > 0 else 0.0
            data.append([coin, f"₩ {p_k:,.2f}", f"{qty:,.6f}"])

        df = pd.DataFrame(data, columns=["자산명", "시세(KRW)", "보유(계산)수량"])
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # 편집창을 루프 내부 container 맨 아래에 배치하여 항상 테이블 밑에 오게 함
        render_editor()

    time.sleep(1)
