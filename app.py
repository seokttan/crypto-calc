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
    """야후 파이낸스에서 실시간 환율 정보 가져오기"""
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/USDKRW=X?interval=1m&range=1d"
        r = requests_cffi.Session(impersonate="chrome").get(url, timeout=5)
        data = r.json()
        price = data['chart']['result'][0]['meta']['regularMarketPrice']
        return float(price)
    except:
        return 1450.0  # 오류 발생 시 기본값

def get_lbank_prices(coins):
    """LBank API를 통해 특정 코인들의 현재가(USDT) 가져오기"""
    try:
        # 모든 티커를 한 번에 가져와서 매핑 (효율성)
        res = requests.get("https://api.lbkex.com/v2/ticker/24hr.do", params={'symbol': 'all'}, timeout=3).json()
        if res.get('result') == 'true':
            # symbol 형식을 'btc_usdt' -> 'BTC'로 변환하여 딕셔너리 생성
            lbank_map = {item['symbol'].replace('_usdt', '').upper(): float(item['ticker']['latest']) for item in res['data']}
            return {coin: lbank_map.get(coin, 0.0) for coin in coins}
        return {coin: 0.0 for coin in coins}
    except:
        return {coin: 0.0 for coin in coins}

# --- [2] 데이터 로드 (쿠키 및 세션) ---
if 'target_coins' not in st.session_state:
    saved_coins = controller.get('my_target_coins')
    # 쿠키에 저장된 값이 없으면 기본 리스트 사용
    st.session_state.target_coins = saved_coins if saved_coins else ['BTC', 'ETH', 'XRP', 'SOL', 'DOGE']

# --- [3] 상단 고정 레이아웃 (입력창) ---
st.title("💰 실시간 자산 환산기")

with st.container():
    st.subheader("계산 기준 설정")
    c1, c2 = st.columns([1, 2])
    with c1:
        # 기준 자산 선택 (목록에 있는 코인들도 포함)
        options = ["KRW", "USDT"] + st.session_state.target_coins
        base_asset = st.selectbox("보유 중인 기준 자산", options)
    with c2:
        default_val = 1000000.0 if base_asset == "KRW" else 1.0
        input_val = st.number_input(f"{base_asset} 수량/금액 입력", min_value=0.0, value=default_val, step=0.1, format="%.6f")

st.divider()

# --- [4] 영역 확보 ---
# 1. 시세 표 영역
result_area = st.empty()

st.write("") 
st.divider()

# 2. 편집창 영역 (하단 고정)
edit_area = st.empty()

# --- [5] 편집창 구현 (유효성 검증 포함) ---
with edit_area.expander("⚙️ 내 자산 리스트 편집 (LBank 상장 코인만 가능)"):
    add_col, del_col = st.columns(2)
    
    with add_col:
        new_coin = st.text_input("추가할 코인 심볼 (예: BTC, PEPE)", key="input_new").upper().strip()
        if st.button("목록에 추가", use_container_width=True):
            if new_coin:
                # [핵심] API를 호출하여 실제로 존재하는 코인인지 확인
                with st.spinner(f'{new_coin} 유효성 확인 중...'):
                    check_price = get_lbank_prices([new_coin])
                
                if check_price.get(new_coin, 0.0) > 0:
                    if new_coin not in st.session_state.target_coins:
                        st.session_state.target_coins.append(new_coin)
                        # 쿠키 저장 (1년 유지)
                        controller.set('my_target_coins', st.session_state.target_coins, max_age=31536000)
                        st.success(f"✅ {new_coin}이(가) 추가되었습니다.")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.warning("이미 목록에 있는 코인입니다.")
                else:
                    st.error(f"❌ '{new_coin}'은(는) LBank에 없거나 시세를 불러올 수 없습니다.")
            else:
                st.info("코인 심볼을 입력해주세요.")

    with del_col:
        if st.session_state.target_coins:
            del_target = st.selectbox("삭제할 코인 선택", st.session_state.target_coins, key="select_del")
            if st.button("목록에서 삭제", use_container_width=True):
                st.session_state.target_coins.remove(del_target)
                controller.set('my_target_coins', st.session_state.target_coins, max_age=31536000)
                st.warning(f"🗑️ {del_target}이(g) 삭제되었습니다.")
                time.sleep(0.5)
                st.rerun()

# --- [6] 실시간 업데이트 루프 ---
while True:
    with result_area.container():
        usd_to_krw = get_exchange_rate()
        coin_prices = get_lbank_prices(st.session_state.target_coins)
        kor_now = datetime.utcnow() + timedelta(hours=9)
        
        st.caption(f"최종 업데이트: {kor_now.strftime('%Y-%m-%d %H:%M:%S')} (1초마다 갱신)")
        
        # 상단 메트릭
        m1, m2 = st.columns(2)
        m1.metric("현재 환율 (USDKRW)", f"₩ {usd_to_krw:,.2f}")
        
        # 기준 자산을 USDT로 환산 (모든 계산의 중심점)
        if base_asset == "KRW":
            base_usdt = input_val / usd_to_krw
        elif base_asset == "USDT":
            base_usdt = input_val
        else:
            # 선택한 기준이 특정 코인일 경우 해당 코인의 USDT 가격을 가져와 곱함
            p_u = coin_prices.get(base_asset, 0.0)
            base_usdt = input_val * p_u if p_u > 0 else 0.0
            
        m2.metric(f"총 가치 (USDT)", f"$ {base_usdt:,.2f}")

        # 데이터프레임 구성
        data = [
            ["🇰🇷 KRW (현금)", f"₩ 1.00", f"₩ {base_usdt * usd_to_krw:,.0f}"],
            ["🇺🇸 USDT (테더)", f"₩ {usd_to_krw:,.2f}", f"{base_usdt:,.2f} USDT"]
        ]
        
        for coin in st.session_state.target_coins:
            p_u = coin_prices.get(coin, 0.0)
            p_k = p_u * usd_to_krw
            # 해당 코인을 몇 개 살 수 있는지 계산
            qty = base_usdt / p_u if p_u > 0 else 0.0
            
            # 가격이 0원인 코인은(상장폐지 등) 표시에서 제외하거나 별도 처리 가능
            if p_u > 0:
                data.append([f"🪙 {coin}", f"₩ {p_k:,.2f}", f"{qty:,.6f} {coin}"])

        df = pd.DataFrame(data, columns=["자산명", "개당 시세(KRW)", f"보유 시 환산 수량"])
        
        # 표 스타일 적용
        st.dataframe(
            df, 
            use_container_width=True, 
            hide_index=True
        )

    # 1초 대기 후 루프 재시작
    time.sleep(1)
