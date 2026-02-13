import streamlit as st
import requests
import base64
import json
from datetime import datetime, timedelta, timezone

# --- 設定區 ---
SCREENPIPE_API_URL = "http://localhost:3030"
OLLAMA_API_URL = "http://localhost:11434"

st.set_page_config(page_title="Screenpipe 回顧助手 (Dev)", layout="wide", page_icon="🧠")

# --- 0. 工具函式 ---

def format_ts(iso_str):
    """將 ISO 時間字串轉為本地易讀格式"""
    try:
        # 處理 Screenpipe 可能回傳的 Z 結尾
        if not iso_str:
            return ""
        if iso_str.endswith("Z"):
            iso_str = iso_str[:-1] + "+00:00"
        dt = datetime.fromisoformat(iso_str)
        # 轉為本地時間 (System Local Time)
        local_dt = dt.astimezone()
        return local_dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return iso_str  # 解析失敗就回傳原字串

def get_ollama_models():
    try:
        response = requests.get(f"{OLLAMA_API_URL}/api/tags", timeout=2)
        if response.status_code == 200:
            return [model['name'] for model in response.json().get('models', [])]
        return []
    except:
        return []

# --- 1. API 串接（可選 include_frames） ---

def query_screenpipe(query_text="", limit=100, start_time=None, end_time=None, include_frames=True, timeout=30):
    endpoint = f"{SCREENPIPE_API_URL}/search"
    params = {"limit": limit, "include_frames": "true" if include_frames else "false"}

    if query_text:
        params["q"] = query_text

    if start_time:
        utc_start = start_time.astimezone(timezone.utc)
        params["start_time"] = utc_start.strftime("%Y-%m-%dT%H:%M:%SZ")
    if end_time:
        utc_end = end_time.astimezone(timezone.utc)
        params["end_time"] = utc_end.strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        response = requests.get(endpoint, params=params, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        return data.get("data", data) if isinstance(data, dict) else data
    except Exception as e:
        st.error(f"Screenpipe API 錯誤: {e}")
        return []

def fetch_frame_near_timestamp(ts_iso, window_seconds=5):
    """針對單一 timestamp 做窄時窗查詢，盡量抓一張圖片（最接近該時間）"""
    try:
        # parse timestamp
        if ts_iso.endswith("Z"):
            ts_iso = ts_iso[:-1] + "+00:00"
        center = datetime.fromisoformat(ts_iso)
    except Exception:
        return None

    start = center - timedelta(seconds=window_seconds)
    end = center + timedelta(seconds=window_seconds)
    results = query_screenpipe("", limit=1, start_time=start, end_time=end, include_frames=True, timeout=20)
    if results and len(results) > 0:
        return results[0]
    return None

# --- 3. Ollama 視覺分析（更新） ---
def analyze_image_with_ollama(base64_image, model_name, keep_alive=None, custom_prompt=None):
    if not base64_image:
        return "無圖片資料"

    default_prompt = """
    [任務] 請看這張電腦截圖。用繁體中文描述「畫面中的主要活動」。
    [限制] 200字內，直接講重點。
    """

    prompt = custom_prompt if custom_prompt else default_prompt

    payload = {
        "model": model_name,
        "prompt": prompt,
        "images": [base64_image],
        "stream": False
    }

    # 如果有設定 keep_alive 就加進去 (Ollama 允許不同型別)
    if keep_alive is not None:
        payload["keep_alive"] = keep_alive

    try:
        response = requests.post(f"{OLLAMA_API_URL}/api/generate", json=payload, timeout=90)
        if response.status_code == 200:
            # Ollama 回傳格式可能包含 response 欄位
            return response.json().get("response", "生成失敗")
        return f"錯誤: {response.status_code}"
    except Exception as e:
        return f"連線錯誤: {e}"

def unload_model(model_name):
    """強制卸載模型釋放 VRAM（保留原來做法）"""
    try:
        # 使用 keep_alive=0 的方式請求，嘗試讓 Ollama 卸載模型
        requests.post(f"{OLLAMA_API_URL}/api/generate", json={"model": model_name, "keep_alive": 0}, timeout=5)
    except Exception:
        pass

def summarize_timeline(timeline_data, model_name):
    txt_block = "\n".join([f"- {t['time']}: {t['desc']}" for t in timeline_data])
    prompt = f"""
    [角色設定]
    你是一位專業的個人助理。你的任務是閱讀使用者的電腦操作紀錄，並用繁體中文寫一份「工作日誌摘要」。

    [原始紀錄]
    {txt_block}

    [指令]
    1. 請根據上述時間點，推測使用者的主要工作內容。
    2. 將零碎的操作歸納為 3~5 個主要活動段落。
    3. 使用「故事性」的敘述方式（例如：「早上你專注於...隨後轉向...」）。
    4. 最後列出條列式重點。

    [嚴格限制]
    - **絕對不要** 輸出 Python 程式碼或 Markdown 代碼框。
    - **絕對不要** 定義函式 (def ...)。
    - **絕對不要** 輸出簡體中文及中國用語。
    - 直接輸出繁體中文的文字報告即可。
    """
    payload = {"model": model_name, "prompt": prompt, "stream": False}
    try:
        res = requests.post(f"{OLLAMA_API_URL}/api/generate", json=payload, timeout=120)
        return res.json().get("response", "摘要失敗") if res.status_code == 200 else "API Error"
    except Exception as e:
        return f"摘要連線錯誤: {e}"

# --- 介面邏輯 ---
st.title("🧠 Screenpipe 記憶回溯 (Dev)")

# --- 側邊欄設定 ---
with st.sidebar:
    st.header("⚙️ 設定與除錯")

    models = get_ollama_models()
    v_idx = models.index("qwen3-vl:2b") if "qwen3-vl:2b" in models else 0
    vision_model = st.selectbox("👁️ Vision Model", models, index=v_idx if models else 0)

    t_idx = models.index("gemma3:4b") if "gemma3:4b" in models else 0
    text_model = st.selectbox("📝 Text Model", models, index=t_idx if models else 0)

    st.divider()
    debug_mode = st.checkbox("🐞 開發者除錯模式 (Debug Mode)", value=False)
    if debug_mode:
        st.info("已開啟：將顯示原始 JSON 與詳細錯誤訊息")

# --- 分頁 ---
tab_search, tab_recap = st.tabs(["🔎 關鍵字搜尋", "⏱️ 時段回顧 (Time Lapse)"])

# ================= Tab 1: 搜尋（使用 Form 防止頻繁 Rerun） =================
with tab_search:
    # 建立一個 Form，設定 clear_on_submit=False 保留輸入內容
    with st.form("search_filter_form"):
        c1, c2 = st.columns([4, 1])
        q_text = c1.text_input("輸入關鍵字 (支援 OCR 文字或 App 名稱)", placeholder="例如: python, youtube, 報表...")
        limit = c2.number_input("筆數限制 (建議 5 筆以免等太久)", 1, 20, 5)
        
        # --- 進階時間過濾區塊 ---
        with st.expander("⏳ 進階時間過濾 (設定後請點擊下方搜尋按鈕)", expanded=False):
            f_col1, f_col2 = st.columns(2)
            
            start_dt = None
            end_dt = None
            
            with f_col1:
                st.caption("🛫 起點限制")
                use_start = st.checkbox("啟用開始時間")
                d1 = st.date_input("開始日期", datetime.now(), key="search_start_date")
                t1 = st.time_input("開始時刻", datetime.strptime("00:00", "%H:%M").time(), key="search_start_time")
                if use_start:
                    start_dt = datetime.combine(d1, t1)
                
            with f_col2:
                st.caption("🛬 終點限制")
                use_end = st.checkbox("啟用結束時間")
                d2 = st.date_input("結束日期", datetime.now(), key="search_end_date")
                t2 = st.time_input("結束時刻", datetime.now().time(), key="search_end_time")
                if use_end:
                    end_dt = datetime.combine(d2, t2)

        # 將原本的 st.button 改為 st.form_submit_button
        submitted = st.form_submit_button("開始搜尋", type="primary", use_container_width=True)

    # 當按下 Form 的送出按鈕後，才開始執行搜尋邏輯
    if submitted:
        if not q_text:
            st.warning("請輸入關鍵字")
        else:
            # 1. 建立一個佔位符
            search_msg_placeholder = st.empty()
            
            # 2. 顯示查詢中訊息
            search_msg_placeholder.info("🔍 正在查詢 Screenpipe 資料庫...")
            
            # 3. 執行搜尋
            search_results = query_screenpipe(
                q_text, 
                limit=limit, 
                start_time=start_dt, 
                end_time=end_dt, 
                include_frames=True
            )

            search_msg_placeholder.empty()

            if search_results:
                st.success(f"✅ 搜尋完成，共搜尋到 {len(search_results)} 筆資料")
                st.divider()
                progress_text = "🤖 AI 正在逐張分析畫面中..."
                my_bar = st.progress(0, text=progress_text)

                for idx, item in enumerate(search_results):
                    content = item.get("content", {})
                    frame_b64 = content.get("frame", "")
                    ts = format_ts(content.get("timestamp", ""))

                    clean_b64 = frame_b64.split(",")[1] if isinstance(frame_b64, str) and "," in frame_b64 else frame_b64

                    col_img, col_desc = st.columns([1, 1.5])

                    with col_img:
                        if clean_b64:
                            try:
                                st.image(base64.b64decode(clean_b64), use_container_width=True)
                            except Exception:
                                st.error("圖片解碼失敗")
                        else:
                            st.error("無影像")

                    with col_desc:
                        st.subheader(f"🕒 {ts}")
                        if clean_b64:
                            with st.spinner(f"AI 正在讀取第 {idx+1} 張截圖..."):
                                search_prompt = """
                                請分析這張螢幕截圖。
                                1. 識別使用者正在使用的軟體。
                                2. 描述畫面中的核心內容（例如正在寫什麼程式碼、看什麼文章、或是聊什麼天）。
                                3. 請用繁體中文回答，長度約 100 字，重點摘要即可。
                                """
                                summary = analyze_image_with_ollama(
                                    clean_b64,
                                    vision_model,
                                    keep_alive=0,
                                    custom_prompt=search_prompt
                                )
                            st.info(f"**AI 分析：**\n\n{summary}")

                        with st.expander("查看原始 OCR 文字"):
                            st.caption(content.get("text", "無文字資料")[:500] + "...")

                    if debug_mode:
                        with st.expander(f"🐞 Debug: 原始資料 (Item {idx})", expanded=False):
                            st.write("Frame Length:", len(clean_b64) if clean_b64 else 0)
                            st.write("Raw Timestamp:", content.get("timestamp"))
                            st.json(item)

                    st.divider()
                    my_bar.progress((idx + 1) / len(search_results), text=f"已完成 {idx + 1}/{len(search_results)}")

                unload_model(vision_model)
                my_bar.empty()
                st.toast("所有分析完成！VRAM 已釋放。", icon="🧹")

# ================= Tab 2: 回顧（改為二階段搜尋 + 摘要置頂） =================
with tab_recap:
    st.info("設定時間範圍，AI 將自動抽樣並生成工作摘要。第一階段只撈 metadata（無圖片），降低超時風險。")
    r_col1, r_col2, r_col3, r_col4 = st.columns(4)
    r_date = r_col1.date_input("日期", datetime.now())
    r_start = r_col2.time_input("開始", datetime.strptime("09:00", "%H:%M").time())
    r_end = r_col3.time_input("結束", datetime.now().time())
    r_samples = r_col4.slider("採樣數", 3, 20, 5)
    window_seconds = st.number_input("每張抓圖時窗（秒, ±）", 1, 30, 5)
    stage1_limit = st.number_input("第一階段最多筆數 (metadata)", 50, 2000, 500)

    if st.button("🎬 生成回顧摘要", type="primary", use_container_width=True):
        # 【修改點 1】先在最上方建立一個空容器佔位
        summary_placeholder = st.empty()

        start_dt = datetime.combine(r_date, r_start)
        end_dt = datetime.combine(r_date, r_end)

        with st.status("🚀 啟動 AI 回顧引擎...", expanded=True) as status:
            # --- Stage 1: 只拿 metadata 避免超時 ---
            st.write("🔍 [1/4] 正在從 Screenpipe 撈取時段內的 metadata（不含圖片）...")
            raw_meta = query_screenpipe("", limit=stage1_limit, start_time=start_dt, end_time=end_dt, include_frames=False, timeout=30)

            if not raw_meta:
                status.update(label="⚠️ 該時段無資料或抓取失敗", state="error")
                st.error("找不到資料，請檢查 Screenpipe 是否有在錄製，或調整時間範圍。")
            else:
                # --- 取出所有 timestamp 並排序 ---
                st.write(f"⚖️ [2/4] 取得 {len(raw_meta)} 筆 metadata，正在進行智慧抽樣...")
                timestamps = []
                for it in raw_meta:
                    try:
                        ts = it.get("content", {}).get("timestamp") or it.get("timestamp")
                        if ts:
                            timestamps.append(ts)
                    except:
                        continue

                if not timestamps:
                    status.update(label="❌ 找不到時間戳", state="error")
                else:
                    # 排序並均勻抽樣
                    timestamps = sorted(timestamps)
                    n_available = len(timestamps)
                    actual_samples = min(r_samples, n_available)
                    
                    if actual_samples == 1:
                        indices = [n_available // 2]
                    else:
                        step = n_available / actual_samples
                        indices = [int(step * i + step/2) for i in range(actual_samples)]
                        indices = [min(max(0, idx), n_available-1) for idx in indices]

                    selected_ts = [timestamps[i] for i in indices]

                    st.write(f"👁️ [3/4] 對選中的 {len(selected_ts)} 個時間點做窄時窗抓圖與單張分析...")
                    
                    timeline = []
                    prog = st.progress(0, text="準備開始...")
                    processed_count = 0
                    total_items = len(selected_ts)
                    
                    # === Grid Layout + Debug 邏輯 ===
                    IMAGES_PER_ROW = 5
                    
                    # 使用 range 做分批處理
                    for i in range(0, total_items, IMAGES_PER_ROW):
                        batch_ts = selected_ts[i : i + IMAGES_PER_ROW]
                        cols = st.columns(len(batch_ts))
                        
                        for idx, ts in enumerate(batch_ts):
                            processed_count += 1
                            prog.progress(processed_count / total_items, text=f"分析進度 {processed_count}/{total_items}")
                            
                            with cols[idx]:
                                item = fetch_frame_near_timestamp(ts, window_seconds=window_seconds)
                                ts_pretty = format_ts(ts)
                                time_only = ts_pretty.split(" ")[1] if " " in ts_pretty else ts_pretty
                                
                                clean_b64 = None
                                desc = "待分析"
                                err_msg = None

                                # 1. 解析圖片
                                if item:
                                    content = item.get("content", {})
                                    raw_frame = content.get("frame")
                                    if raw_frame and isinstance(raw_frame, str):
                                        if "," in raw_frame:
                                            clean_b64 = raw_frame.split(",")[1]
                                        elif len(raw_frame) > 100:
                                            clean_b64 = raw_frame
                                    else:
                                        err_msg = "Frame欄位無效"
                                else:
                                    err_msg = "查無資料"
                                
                                # 2. 顯示卡片
                                with st.container(border=True):
                                    st.caption(f"⏱️ {time_only}")
                                    
                                    if clean_b64:
                                        try:
                                            img_data = base64.b64decode(clean_b64)
                                            st.image(img_data, use_container_width=True)
                                            
                                            with st.spinner("AI 👀"):
                                                search_prompt = "簡述畫面活動(軟體/內容)，繁體中文50字內。"
                                                ai_res = analyze_image_with_ollama(clean_b64, vision_model, keep_alive=0, custom_prompt=search_prompt)
                                                
                                                if ai_res.startswith("錯誤:") or ai_res.startswith("連線錯誤") or "生成失敗" in ai_res:
                                                    desc = "分析失敗"
                                                    err_msg = ai_res
                                                else:
                                                    desc = ai_res
                                                    timeline.append({"time": ts_pretty, "desc": desc})
                                                    # 成功顯示描述
                                                    st.markdown(f"<small>{desc}</small>", unsafe_allow_html=True)

                                        except Exception as e:
                                            st.error("圖片解碼錯誤")
                                            err_msg = str(e)
                                    else:
                                        st.info("無截圖")
                                        st.caption(err_msg if err_msg else "No Image")

                                    if debug_mode:
                                        with st.expander("🐞 Debug"):
                                            st.text(f"TS: {ts}")
                                            if err_msg:
                                                st.error(err_msg)

                        st.write("") 
                    
                    unload_model(vision_model)
                    prog.empty()

                    # --- Stage 4: Summarize ---
                    st.write(f"📝 [4/4] 使用 {text_model} 生成最終報告...")
                    if timeline:
                        summary = summarize_timeline(timeline, text_model)
                        status.update(label="✅ 回顧分析完成！", state="complete", expanded=False) # 縮起來讓上面的報告更明顯
                        
                        # 【修改點 2】將結果寫入最上方的佔位容器
                        with summary_placeholder.container():
                            st.success("🎉 分析完成！以下是您的工作日誌摘要：")
                            st.subheader("📋 AI 摘要工作日誌")
                            st.markdown(summary)
                            st.divider() # 加個分隔線區隔下方的圖片
                    else:
                        status.update(label="❌ 無有效圖片可分析", state="error")