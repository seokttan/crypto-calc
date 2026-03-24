import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from streamlit_cookies_controller import CookieController
from curl_cffi import requests as requests_cffi

# --- [1] 초기 설정 및 스타일 ---
st.set_page_config(page_title="Real-time Asset Sync", layout="centered")

# CSS를 이용해 데이터프레임 업데이트 시 애니메이션 효과 최소화
st.markdown("""
    <style>
    .stDataFrame {transition: none !important;}
    </style>
    """, unsafe_allow_html=True)

controller = CookieController()

@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/USDKRW=X?interval=1m&range=1d"
        r = requests_cffi.Session(impersonate="chrome").get(url, timeout=5)
        data = r.json()
        price = data['chart']['result'][0]['meta']['regularMarketPrice']
        return float(price)
    except:
        return 1420.0

def get_lbank_prices(coins):
    try:
        res = requests.get("https://api.lbkex.com/v2/ticker/24hr.do", params={'symbol': 'all'}, timeout=2).json()
        if res.get('result') == 'true':
            lbank_map = {item['symbol'].replace('_usdt', '').upper(): float(item['ticker']['latest']) for item in res['data']}
            return {coin: lbank_map.get(coin, 0.0) for coin in coins}
        return {coin: 0.0 for coin in coins}
    except:
        return {coin: 0.0 for coin in coins}

# --- [2] 데이터 로드 (세션/쿠키) ---
if 'target_coins' not in st.session_state:
    saved_coins = controller.get('my_target_coins')
    st.session_state.target_coins = saved_coins if saved_coins else ['BTC', 'ETH', 'XRP', 'SOL', 'DOGE']

# --- [3] 상단 고정 UI ---
st.title("💰 실시간 자산 계산기")

with st.container():
    st.subheader("계산 기준 설정")
    c1, c2 = st.columns([1, 2])
    with c1:
        base_asset = st.selectbox("기준 자산", ["KRW", "USDT"] + st.session_state.target_coins, key="main_base_asset")
    with c2:
        default_val = 1000000.0 if base_asset == "KRW" else 1.0
        input_val = st.number_input("수량/금액 입력", min_value=0.0, value=default_val, step=1.0, key="main_input_val")

st.divider()

# --- [4] 실시간 업데이트 영역 (Fragment) ---
# 이 함수 내부만 2초마다 '조용히' 업데이트됩니다.
@st.fragment(run_every=2)
def live_sync_area(base_asset, input_val):
    usd_to_krw = get_exchange_rate()
    coin_prices = get_lbank_prices(st.session_state.target_coins)
    kor_now = datetime.utcnow() + timedelta(hours=9)
    
    st.caption(f"⚡ 실시간 동기화 중... (KST {kor_now.strftime('%H:%M:%S')})")
    
    # 상단 환율 메트릭
    st.metric("현재 환율 (USDKRW)", f"₩ {usd_to_krw:,.2f}")

    # 계산 로직
    if base_asset == "KRW":
        base_usdt = input_val / usd_to_krw
    elif base_asset == "USDT":
        base_usdt = input_val
    else:
        p_u = coin_prices.get(base_asset, 0.0)
        base_usdt = input_val * p_u if p_u > 0 else 0.0

    # 데이터 구성
    data = [
        {"자산명": "KRW", "시세(KRW)": "₩ 1.00", "보유(계산)수량": f"{base_usdt * usd_to_krw:,.0f}"},
        {"자산명": "USDT", "시세(KRW)": f"₩ {usd_to_krw:,.2f}", "보유(계산)수량": f"{base_usdt:,.2f}"}
    ]
    
    for coin in st.session_state.target_coins:
        p_u = coin_prices.get(coin, 0.0)
        p_k = p_u * usd_to_krw
        qty = base_usdt / p_u if p_u > 0 else 0.0
        data.append({
            "자산명": coin, 
            "시세(KRW)": f"₩ {p_k:,.2f}", 
            "보유(계산)수량": f"{qty:,.6f}"
        })

    # 테이블 출력
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)

# 프래그먼트 실행
live_sync_area(base_asset, input_val)

st.divider()

# --- [5] 하단 자산 편집창 ---
with st.expander("⚙️ 내 자산 리스트 편집"):
    add_col, del_col = st.columns(2)
    with add_col:
        new_coin = st.text_input("추가할 심볼", key="edit_add").upper().strip()
        if st.button("목록 추가", key="btn_add"):
            if new_coin and new_coin not in st.session_state.target_coins:
                st.session_state.target_coins.append(new_coin)
                controller.set('my_target_coins', st.session_state.target_coins, max_age=31536000)
                st.rerun()
    with del_col:
        if st.session_state.target_coins:
            del_target = st.selectbox("삭제할 코인", st.session_state.target_coins, key="edit_del")
            if st.button("목록 삭제", key="btn_del"):
                st.session_state.target_coins.remove(del_target)
                controller.set('my_target_coins', st.session_state.target_coins, max_age=31536000)
                st.rerun()
