import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from streamlit_cookies_controller import CookieController
from curl_cffi import requests as requests_cffi

# --- [1] 초기 설정 및 데이터 함수 ---
st.set_page_config(page_title="Real-time Asset Sync", layout="centered")
controller = CookieController()

@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        # Yahoo Finance API (curl_cffi 사용)
        url = "https://query1.finance.yahoo.com/v8/finance/chart/USDKRW=X?interval=1m&range=1d"
        r = requests_cffi.Session(impersonate="chrome").get(url, timeout=5)
        data = r.json()
        price = data['chart']['result'][0]['meta']['regularMarketPrice']
        return float(price)
    except:
        return 1450.0  # 실패 시 기본값

def get_lbank_prices(coins):
    try:
        res = requests.get("https://api.lbkex.com/v2/ticker/24hr.do", params={'symbol': 'all'}, timeout=2).json()
        if res.get('result') == 'true':
            lbank_map = {item['symbol'].replace('_usdt', '').upper(): float(item['ticker']['latest']) for item in res['data']}
            return {coin: lbank_map.get(coin, 0.0) for coin in coins}
        return {coin: 0.0 for coin in coins}
    except:
        return {coin: 0.0 for coin in coins}

# --- [2] 세션 상태 및 쿠키 로드 ---
if 'target_coins' not in st.session_state:
    saved_coins = controller.get('my_target_coins')
    st.session_state.target_coins = saved_coins if saved_coins else ['BTC', 'ETH', 'XRP', 'SOL', 'DOGE']

# --- [3] UI 상단: 고정 입력 영역 ---
st.title("💰 실시간 자산 동기화")

with st.container():
    st.subheader("계산 기준 설정")
    c1, c2 = st.columns([1, 2])
    with c1:
        base_asset = st.selectbox("기준 자산", ["KRW", "USDT"] + st.session_state.target_coins)
    with c2:
        default_val = 1000000.0 if base_asset == "KRW" else 1.0
        input_val = st.number_input("수량/금액 입력", min_value=0.0, value=default_val, step=1.0)

st.divider()

# --- [4] UI 중간: 실시간 결과 출력 영역 (Placeholder) ---
# 이 자리에 실시간 표가 계속 업데이트됩니다.
result_placeholder = st.empty()

st.write("") # 여백
st.divider()

# --- [5] UI 하단: 자산 리스트 편집 영역 (Placeholder) ---
# while 루프보다 위에 선언되어야 NameError를 방지할 수 있습니다.
edit_placeholder = st.empty()

with edit_placeholder.expander("⚙️ 내 자산 리스트 편집 (쿠키 저장)"):
    add_col, del_col = st.columns(2)
    with add_col:
        new_coin = st.text_input("추가할 심볼 (예: SOL)", key="add_coin_input").upper().strip()
        if st.button("목록 추가"):
            if new_coin and new_coin not in st.session_state.target_coins:
                st.session_state.target_coins.append(new_coin)
                controller.set('my_target_coins', st.session_state.target_coins, max_age=31536000)
                st.success(f"{new_coin} 추가됨")
                time.sleep(0.5)
                st.rerun()
    with del_col:
        if st.session_state.target_coins:
            del_coin = st.selectbox("삭제할 코인 선택", st.session_state.target_coins, key="del_coin_select")
            if st.button("목록 삭제"):
                st.session_state.target_coins.remove(del_coin)
                controller.set('my_target_coins', st.session_state.target_coins, max_age=31536000)
                st.warning(f"{del_coin} 삭제됨")
                time.sleep(0.5)
                st.rerun()

# --- [6] 실시간 무한 루프 ---
# 루프가 시작되면 이 아래의 코드는 실행되지 않으므로, 모든 UI 선언은 이 위에 있어야 합니다.
while True:
    with result_placeholder.container():
        usd_to_krw = get_exchange_rate()
        coin_prices = get_lbank_prices(st.session_state.target_coins)
        kor_now = datetime.utcnow() + timedelta(hours=9)
        
        st.caption(f"최종 업데이트: {kor_now.strftime('%H:%M:%S')}")
        st.metric("현재 환율 (USDKRW)", f"₩ {usd_to_krw:,.2f}")

        # 계산 로직
        if base_asset == "KRW":
            base_usdt = input_val / usd_to_krw
        elif base_asset == "USDT":
            base_usdt = input_val
        else:
            p_u = coin_prices.get(base_asset, 0.0)
            base_usdt = input_val * p_u if p_u > 0 else 0.0

        # 테이블 데이터 생성
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

    # 1초 대기
    time.sleep(1)
