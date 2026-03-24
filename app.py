import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from streamlit_cookies_controller import CookieController
from curl_cffi import requests as requests_cffi

# --- [1] 초기 설정 ---
st.set_page_config(page_title="Real-time Asset Sync", layout="wide")
controller = CookieController()

@st.cache_data(ttl=60)
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
        res = requests.get("https://api.lbkex.com/v2/ticker/24hr.do", params={'symbol': 'all'}, timeout=3).json()
        if res.get('result') == 'true':
            lbank_map = {item['symbol'].replace('_usdt', '').upper(): float(item['ticker']['latest']) for item in res['data']}
            return {coin: lbank_map.get(coin, 0.0) for coin in coins}
        return {coin: 0.0 for coin in coins}
    except:
        return {coin: 0.0 for coin in coins}

# --- [2] 데이터 로드 (쿠키 및 세션) ---
if 'target_coins' not in st.session_state:
    saved_coins = controller.get('my_target_coins')
    st.session_state.target_coins = saved_coins if saved_coins else ['BTC', 'ETH', 'XRP', 'SOL', 'DOGE']

# --- [3] 상단 고정 레이아웃 (입력창) ---
# 타이틀 제거됨

with st.container():
    st.subheader("계산 기준 설정")
    c1, c2 = st.columns([1, 2])
    with c1:
        options = ["KRW", "USDT"] + st.session_state.target_coins
        base_asset = st.selectbox("보유 중인 기준 자산", options)
    with c2:
        default_val = 1000000.0 if base_asset == "KRW" else 1.0
        input_val = st.number_input(f"{base_asset} 수량/금액 입력", min_value=0.0, value=default_val, step=0.1, format="%.6f")

st.divider()

# --- [4] 영역 확보 ---
result_area = st.empty()
st.write("") 
st.divider()
edit_area = st.empty()

# --- [5] 편집창 구현 (문구 수정됨) ---
with edit_area.expander("⚙️ 내 자산 리스트 편집"):
    add_col, del_col = st.columns(2)
    
    with add_col:
        new_coin = st.text_input("추가할 코인 심볼 (예: BTC)", key="input_new").upper().strip()
        if st.button("목록에 추가", use_container_width=True):
            if new_coin:
                with st.spinner(f'확인 중...'):
                    check_price = get_lbank_prices([new_coin])
                
                if check_price.get(new_coin, 0.0) > 0:
                    if new_coin not in st.session_state.target_coins:
                        st.session_state.target_coins.append(new_coin)
                        controller.set('my_target_coins', st.session_state.target_coins, max_age=31536000)
                        st.success(f"✅ {new_coin} 추가 완료")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.warning("이미 목록에 있는 코인입니다.")
                else:
                    st.error(f"❌ '{new_coin}'은(는) 존재하지 않는 심볼입니다.")
            else:
                st.info("코인 심볼을 입력해주세요.")

    with del_col:
        if st.session_state.target_coins:
            del_target = st.selectbox("삭제할 코인 선택", st.session_state.target_coins, key="select_del")
            if st.button("목록에서 삭제", use_container_width=True):
                st.session_state.target_coins.remove(del_target)
                controller.set('my_target_coins', st.session_state.target_coins, max_age=31536000)
                st.warning(f"🗑️ {del_target} 삭제됨")
                time.sleep(0.5)
                st.rerun()

# --- [6] 실시간 업데이트 루프 ---
while True:
    with result_area.container():
        usd_to_krw = get_exchange_rate()
        coin_prices = get_lbank_prices(st.session_state.target_coins)
        kor_now = datetime.utcnow() + timedelta(hours=9)
        
        st.caption(f"Update: {kor_now.strftime('%H:%M:%S')}")
        
        # 환율 메트릭만 유지 (총 가치 USDT 제거됨)
        st.metric("현재 환율 (USDKRW)", f"₩ {usd_to_krw:,.2f}")
        
        if base_asset == "KRW":
            base_usdt = input_val / usd_to_krw
        elif base_asset == "USDT":
            base_usdt = input_val
        else:
            p_u = coin_prices.get(base_asset, 0.0)
            base_usdt = input_val * p_u if p_u > 0 else 0.0

        # 데이터프레임 구성
        data = [
            ["🇰🇷 KRW (현금)", f"₩ 1.00", f"₩ {base_usdt * usd_to_krw:,.0f}"],
            ["🇺🇸 USDT (테더)", f"₩ {usd_to_krw:,.2f}", f"{base_usdt:,.2f} USDT"]
        ]
        
        for coin in st.session_state.target_coins:
            p_u = coin_prices.get(coin, 0.0)
            p_k = p_u * usd_to_krw
            qty = base_usdt / p_u if p_u > 0 else 0.0
            
            if p_u > 0:
                data.append([f"🪙 {coin}", f"₩ {p_k:,.2f}", f"{qty:,.6f} {coin}"])

        df = pd.DataFrame(data, columns=["자산명", "개당 시세(KRW)", "환산 수량"])
        st.dataframe(df, use_container_width=True, hide_index=True)

    time.sleep(1)
