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
        return 1420.0  # 실패 시 최근 근사치

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
st.set_page_config(page_title="Real-time Asset Sync", layout="centered")

# 쿠키 로드 (최초 1회)
if 'target_coins' not in st.session_state:
    saved_coins = controller.get('my_target_coins')
    st.session_state.target_coins = saved_coins if saved_coins else ['BTC', 'ETH', 'XRP', 'SOL', 'DOGE']

# --- [3] 고정 UI 영역 (루프 밖에 배치하여 중복 방지) ---

# 1. 자산 편집창 (이제 하나만 나타납니다)
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

# 2. 기준 설정 입력창
with st.container():
    st.subheader("계산 기준 설정")
    c1, c2 = st.columns([1, 2])
    with c1:
        base_asset = st.selectbox("기준 자산", ["KRW", "USDT"] + st.session_state.target_coins)
    with c2:
        default_val = 1000000.0 if base_asset == "KRW" else 1.0
        input_val = st.number_input("수량/금액 입력", min_value=0.0, value=default_val, step=1.0)

st.divider()

# 3. 실시간 결과가 출력될 빈 공간 (Placeholder)
placeholder = st.empty()

# --- [4] 실시간 루프 (결과 표만 업데이트) ---
while True:
    # 루프 안에서는 placeholder만 사용하여 화면을 새로 그립니다.
    with placeholder.container():
        usd_to_krw = get_exchange_rate()
        coin_prices = get_lbank_prices(st.session_state.target_coins)
        kor_now = datetime.utcnow() + timedelta(hours=9)
        
        # 상단 정보 업데이트
        st.caption(f"안전 모드 (curl_cffi) | KST {kor_now.strftime('%H:%M:%S')}")
        st.metric("현재 환율 (USDKRW)", f"₩ {usd_to_krw:,.2f}")

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

    # 1초 대기 (서버 부하 방지 및 실시간성 유지)
    time.sleep(1)

자산 리스트 편집을 맨 밑으로 옮겨라
