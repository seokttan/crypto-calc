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
        url = "https://query1.finance.yahoo.com/v8/finance/chart/USDKRW=X?interval=1m&range=1d"
        r = requests_cffi.Session(impersonate="chrome").get(url, timeout=5)
        data = r.json()
        price = data['chart']['result'][0]['meta']['regularMarketPrice']
        return float(price)
    except:
        return 1425.0

def get_lbank_prices(coins):
    try:
        res = requests.get("https://api.lbkex.com/v2/ticker/24hr.do", params={'symbol': 'all'}, timeout=2).json()
        if res.get('result') == 'true':
            lbank_map = {item['symbol'].replace('_usdt', '').upper(): float(item['ticker']['latest']) for item in res['data']}
            return {coin: lbank_map.get(coin, 0.0) for coin in coins}
        return {coin: 0.0 for coin in coins}
    except:
        return {coin: 0.0 for coin in coins}

# --- [2] UI 설정 ---
st.set_page_config(page_title="Asset Intelligence", layout="centered")

if 'target_coins' not in st.session_state:
    saved_coins = controller.get('my_target_coins')
    st.session_state.target_coins = saved_coins if saved_coins else ['BTC', 'ETH', 'XRP', 'SOL', 'DOGE']

st.title("🌐 Multi-Asset Calc")

# --- [3] 기준 설정 (상단 고정) ---
c1, c2 = st.columns([1, 2])
with c1:
    base_asset = st.selectbox("기준 자산", ["KRW", "USDT"] + st.session_state.target_coins, key="main_base_asset")
with c2:
    default_val = 1000000.0 if base_asset == "KRW" else 1.0
    input_val = st.number_input("수량/금액 입력", min_value=0.0, value=default_val, step=1.0, key="main_input_val")

st.divider()

# --- [4] 실시간 업데이트 영역 (Fragment) ---
# 테이블 전체를 리셋하지 않고 데이터프레임의 내용만 업데이트합니다.
@st.fragment(run_every=1)
def update_results():
    usd_to_krw = get_exchange_rate()
    coin_prices = get_lbank_prices(st.session_state.target_coins)
    kor_now = datetime.utcnow() + timedelta(hours=9)
    
    # 캡션에 시간과 환율 표시
    st.caption(f"KST {kor_now.strftime('%H:%M:%S')} | 환율 ₩ {usd_to_krw:,.2f}")

    # 계산 로직
    if base_asset == "KRW":
        base_usdt = input_val / usd_to_krw
    elif base_asset == "USDT":
        base_usdt = input_val
    else:
        p_u = coin_prices.get(base_asset, 0.0)
        base_usdt = input_val * p_u if p_u > 0 else 0.0

    # 데이터 생성
    data = [
        {"자산명": "KRW", "시세(KRW)": "₩ 1.00", "보유수량": f"{base_usdt * usd_to_krw:,.0f}"},
        {"자산명": "USDT", "시세(KRW)": f"₩ {usd_to_krw:,.2f}", "보유수량": f"{base_usdt:,.2f}"}
    ]
    
    for coin in st.session_state.target_coins:
        p_u = coin_prices.get(coin, 0.0)
        p_k = p_u * usd_to_krw
        qty = base_usdt / p_u if p_u > 0 else 0.0
        data.append({"자산명": coin, "시세(KRW)": f"₩ {p_k:,.2f}", "보유수량": f"{qty:,.6f}"})

    # [핵심] st.dataframe 대신 st.data_editor를 사용하여 인덱스를 숨기고 
    # 데이터만 업데이트되는 연출을 합니다 (수정은 불가능하게 disabled 처리)
    df = pd.DataFrame(data)
    st.dataframe(
        df, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "자산명": st.column_config.TextColumn("자산명"),
            "시세(KRW)": st.column_config.TextColumn("시세(KRW)"),
            "보유수량": st.column_config.TextColumn("보유수량")
        }
    )

update_results()

# --- [5] 자산 리스트 편집 (최하단 고정) ---
st.write("") 
with st.expander("⚙️ 내 자산 리스트 편집 (쿠키 저장)"):
    add_col, del_col = st.columns(2)
    with add_col:
        new_coin = st.text_input("추가할 코인 심볼 (예: SOL)", key="add_input").upper().strip()
        if st.button("추가", key="btn_add"):
            if new_coin and new_coin not in st.session_state.target_coins:
                st.session_state.target_coins.append(new_coin)
                controller.set('my_target_coins', st.session_state.target_coins, max_age=31536000)
                st.rerun()
    with del_col:
        if st.session_state.target_coins:
            del_coin = st.selectbox("삭제할 코인 선택", st.session_state.target_coins, key="del_select")
            if st.button("삭제", key="btn_del"):
                st.session_state.target_coins.remove(del_coin)
                controller.set('my_target_coins', st.session_state.target_coins, max_age=31536000)
                st.rerun()
