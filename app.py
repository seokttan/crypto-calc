import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from streamlit_cookies_controller import CookieController
from curl_cffi import requests as requests_cffi
from streamlit_autorefresh import st_autorefresh  # 추가됨

# --- [1] 초기 설정 ---
st.set_page_config(page_title="Real-time Asset Sync", layout="centered")
controller = CookieController()

# 5초마다 페이지를 자동으로 새로고침 (중복 생성 방지 및 실시간성 유지)
st_autorefresh(interval=5000, key="datarefresh")

@st.cache_data(ttl=60) # 환율은 1분 단위로 캐싱
def get_exchange_rate():
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/USDKRW=X?interval=1m&range=1d"
        r = requests_cffi.Session(impersonate="chrome").get(url, timeout=5)
        data = r.json()
        price = data['chart']['result'][0]['meta']['regularMarketPrice']
        return float(price)
    except:
        return 1450.0

def get_lbank_prices(coins):
    try:
        res = requests.get("https://api.lbkex.com/v2/ticker/24hr.do", params={'symbol': 'all'}, timeout=2).json()
        if res.get('result') == 'true':
            lbank_map = {item['symbol'].replace('_usdt', '').upper(): float(item['ticker']['latest']) for item in res['data']}
            return {coin: lbank_map.get(coin, 0.0) for coin in coins}
        return {coin: 0.0 for coin in coins}
    except:
        return {coin: 0.0 for coin in coins}

# --- [2] 데이터 로드 (쿠키) ---
if 'target_coins' not in st.session_state:
    saved_coins = controller.get('my_target_coins')
    st.session_state.target_coins = saved_coins if saved_coins else ['BTC', 'ETH', 'XRP', 'SOL', 'DOGE']

# --- [3] 상단: 계산 기준 설정 ---
st.title("💰 실시간 자산 계산기")

with st.container():
    st.subheader("계산 기준 설정")
    c1, c2 = st.columns([1, 2])
    with c1:
        base_asset = st.selectbox("기준 자산", ["KRW", "USDT"] + st.session_state.target_coins, key="base_asset_select")
    with c2:
        default_val = 1000000.0 if base_asset == "KRW" else 1.0
        input_val = st.number_input("수량/금액 입력", min_value=0.0, value=default_val, step=1.0, key="input_val_num")

st.divider()

# --- [4] 중간: 실시간 시세 표 (자동 새로고침 대상) ---
usd_to_krw = get_exchange_rate()
coin_prices = get_lbank_prices(st.session_state.target_coins)
kor_now = datetime.utcnow() + timedelta(hours=9)

st.caption(f"최종 업데이트: {kor_now.strftime('%H:%M:%S')} (5초마다 갱신)")
st.metric("현재 환율 (USDKRW)", f"₩ {usd_to_krw:,.2f}")

# 계산 로직
if base_asset == "KRW":
    base_usdt = input_val / usd_to_krw
elif base_asset == "USDT":
    base_usdt = input_val
else:
    p_u = coin_prices.get(base_asset, 0.0)
    base_usdt = input_val * p_u if p_u > 0 else 0.0

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

st.divider()

# --- [5] 하단: 자산 리스트 편집 (맨 아래에 하나만 표시) ---
with st.expander("⚙️ 내 자산 리스트 편집"):
    add_col, del_col = st.columns(2)
    with add_col:
        new_coin = st.text_input("추가할 심볼", key="add_input_final").upper().strip()
        if st.button("목록에 추가", key="add_btn_final"):
            if new_coin and new_coin not in st.session_state.target_coins:
                st.session_state.target_coins.append(new_coin)
                controller.set('my_target_coins', st.session_state.target_coins, max_age=31536000)
                st.rerun()
    with del_col:
        if st.session_state.target_coins:
            del_target = st.selectbox("삭제할 코인 선택", st.session_state.target_coins, key="del_sel_final")
            if st.button("목록에서 삭제", key="del_btn_final"):
                st.session_state.target_coins.remove(del_target)
                controller.set('my_target_coins', st.session_state.target_coins, max_age=31536000)
                st.rerun()
