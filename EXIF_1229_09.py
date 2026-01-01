# 사전
# pip install pandas
#  실행
# streamlit run EXIF_1229_08.py
#######################################################################
#1. st.session_state['history'] 사용:
#     Streamlit은 원래 위젯을 건드리면 전체 코드가 다시 실행되면서 변수가 초기화됩니다.
#     session_state를 사용하면 새로고침이 되어도 history라는 리스트 안에 사진과 정보를 계속 보관할 수 있습니다.
#2. history.append(...):
#    파일이 업로드될 때마다, 기존 데이터를 지우지 않고 리스트 끝에 새로운 사진 정보를 추가합니다.
#3. reversed(...) 반복문:
#     화면에 보여줄 때는 reversed를 사용하여 가장 최근에 올린 사진이 맨 위에 오도록 했습니다. 
#    (블로그 포스팅처럼 쌓이는 방식)
#4. 중복 방지 로직:
#     Streamlit 업로더 특성상 화면 갱신 시 동일 파일이 재처리될 수 있어, 
#     파일 이름(uploaded_file.name)을 체크하여 이미 리스트에 있다면 다시 추가하지 않도록 했습니다.
#
# 5.기록 지우기 버튼:
#       사진이 너무 많이 쌓이면 지저분해지므로, 사이드바에 "모든 기록 지우기" 버튼을 두어 history를 비울 수 있게 했습니다.
#
#6. round(1 / val): 
#     입력된 소수(float) 값의 역수를 취한 뒤 반올림합니다.
#     예: 0.016666667 (1/60초) → 1 / 0.016666667 = 59.9999... → 60
#
# 7.  int(...): 소수점을 떼고 정수로 만듭니다.
#
#8.  f"1/{denom}s": 최종적으로 1/60s 형태로 문자열을 만듭니다.
#       이제 0.1은 1/10s로, 0.004는 1/250s로 우리가 흔히 아는 방식으로 깔끔하게 표시됩니다.
#
#9. 동시에 여러장의 사진을 Drag and Drop했을경우에도 처리하는 코드로 수정
#
# 10. 촬영모드 표시 추가 
#
# 11. 사진에 흰색으로 틀(액자) 만드는 기능 추가
#
# 12. Web으로 확인
#      https://photo-viewer-kentlee.streamlit.app/
#        https://bit.ly/Photo_View_KL
#
# 13. 노출보정정보도 표시
#####################################################################

##

import streamlit as st
import pandas as pd
from PIL import Image, ImageOps 
from PIL.ExifTags import TAGS
import sys
import os
from streamlit.web import cli as stcli
import math 

# --- [설정] 분석할 태그 및 한글 명칭 ---
TARGET_TAGS = {
    "Make": "카메라 제조사",
    "Model": "카메라 모델명",
    "DateTimeOriginal": "촬영 일시",
    "DateTime": "촬영 일시",
    "ExposureProgram": "촬영 모드",
    "ExposureTime": "셔터 스피드",
    "ISOSpeedRatings": "ISO 감도",
    "FNumber": "조리개 값",
    "ExposureBiasValue": "노출 보정", # <<< [추가됨] 노출 보정 항목
    "FocalLength": "초점 거리",
    "LensModel": "렌즈 모델명"
}

# --- [함수] 값 포맷팅 (보기 좋게 변환) ---
def format_value(tag_name, value):
    try:
        # 1. 촬영 모드 변환
        if tag_name == "ExposureProgram":
            mode_map = {
                0: "알 수 없음", 1: "매뉴얼 모드 (M)", 2: "프로그램 모드 (P)",
                3: "조리개 우선 (Av/A)", 4: "셔터 우선 (Tv/S)", 5: "크리에이티브 (Slow)",
                6: "액션 (High speed)", 7: "인물 모드", 8: "풍경 모드"
            }
            return mode_map.get(int(value), f"기타 ({value})")

        # 2. 셔터 스피드 (분수 변환)
        if tag_name == "ExposureTime":
            val = float(value)
            if val >= 1.0:
                return f"{int(val)}s" if val.is_integer() else f"{val}s"
            else:
                denom = int(round(1 / val))
                return f"1/{denom}s"

        # 3. 초점 거리 (mm 추가)
        if tag_name == "FocalLength":
            if isinstance(value, (tuple, list)) and len(value) >= 2 and value[1] != 0:
                fl_val = value[0] / value[1]
            else:
                fl_val = float(value)
            fl_val = round(fl_val, 1)
            if fl_val.is_integer(): fl_val = int(fl_val)
            return f"{fl_val}mm"

        # 4. 조리개 (F값)
        if tag_name == "FNumber":
            return f"f/{round(float(value), 1)}"

        # 5. ISO
        if tag_name == "ISOSpeedRatings":
             val = value[0] if isinstance(value, (list, tuple)) else value
             return f"ISO {val}"

        # 6. [추가됨] 노출 보정 (eV 단위 및 부호 표시)
        if tag_name == "ExposureBiasValue":
            val = float(value)
            if val == 0:
                return "0 eV"
            # + 부호를 강제로 붙여서 표시 (예: +0.3 eV, -0.7 eV)
            return f"{val:+.1f} eV"

    except Exception:
        return value
    return value

# --- [함수] EXIF 정보 추출 ---
def get_detailed_exif(image):
    exif_data = image.getexif()
    if not exif_data: return None
    all_exif = {}
    for tag_id, value in exif_data.items():
        tag_name = TAGS.get(tag_id, tag_id)
        all_exif[tag_name] = value

    if 34665 in exif_data:
        try:
            sub_ifd = exif_data.get_ifd(34665)
            for tag_id, value in sub_ifd.items():
                tag_name = TAGS.get(tag_id, tag_id)
                all_exif[tag_name] = value
        except: pass

    result_dict = {}
    date_val = all_exif.get("DateTimeOriginal", all_exif.get("DateTime"))
    if date_val: result_dict[TARGET_TAGS["DateTimeOriginal"]] = date_val

    for eng_key, kor_name in TARGET_TAGS.items():
        if eng_key in ["DateTime", "DateTimeOriginal"]: continue
        if eng_key in all_exif:
            result_dict[kor_name] = format_value(eng_key, all_exif[eng_key])
    return result_dict

# --- [함수] 흰색 테두리(액자) 추가 ---
def add_white_border(image, border_width_mm=1.0):
    dpi = image.info.get('dpi', (96, 96))[0]
    border_px = math.ceil(dpi / 25.4 * border_width_mm)
    bordered_image = ImageOps.expand(image, border=border_px, fill='white')
    return bordered_image

# --- [메인 화면 구성 함수] ---
def main():
    st.set_page_config(page_title="EXIF 다중 뷰어", layout="wide")
    st.markdown("""<style>th, td { text-align: left !important; }</style>""", unsafe_allow_html=True)

    # 타이틀 변경
    st.title("📷 사진 정보 뷰어 (노출보정 추가)")

    if 'history' not in st.session_state:
        st.session_state['history'] = []

    with st.sidebar:
        st.header("설정")
        if st.button("모든 기록 지우기"):
            st.session_state['history'] = []
            st.rerun()

    uploaded_files = st.file_uploader(
        "여러 장의 이미지를 드래그하거나 선택하세요", 
        type=["jpg", "jpeg", "png"], 
        accept_multiple_files=True
    )

    if uploaded_files:
        for uploaded_file in uploaded_files:
            is_duplicate = any(item['name'] == uploaded_file.name for item in st.session_state['history'])
            if not is_duplicate:
                try:
                    original_image = Image.open(uploaded_file)
                    exif_info = get_detailed_exif(original_image)
                    bordered_image = add_white_border(original_image, border_width_mm=1.0)

                    st.session_state['history'].append({
                        'name': uploaded_file.name,
                        'image': bordered_image, 
                        'exif': exif_info
                    })
                except Exception as e:
                    st.error(f"{uploaded_file.name} 처리 중 오류 발생: {e}")

    if st.session_state['history']:
        st.divider()
        st.caption(f"총 {len(st.session_state['history'])}장의 사진이 등록되었습니다.")
        for idx, item in enumerate(reversed(st.session_state['history'])):
            st.markdown(f"### 🖼️ {item['name']}")
            col1, col2 = st.columns([1, 1])
            with col1:
                st.image(item['image'], use_container_width=True)
            with col2:
                if item['exif']:
                    df = pd.DataFrame(list(item['exif'].items()), columns=["항목", "정보"])
                    st.table(df)
                else:
                    st.warning("정보 없음")
            st.divider()

# --- [자동 실행 로직] ---
if __name__ == "__main__":
    if st.runtime.exists():
        main()
    else:
        sys.argv = ["streamlit", "run", os.path.abspath(__file__)]
        sys.exit(stcli.main())