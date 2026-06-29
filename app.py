import streamlit as st
import pandas as pd

st.set_page_config(page_title="W杯サッカーくじ集計システム", layout="wide")

# スプレッドシートのベースURL
BASE_URL = "https://docs.google.com/spreadsheets/d/1_vlPH_Yl5zYKT4-5p5POZZLM1cJPbYwQ0yzUjF0FinA"

# 各シートのID
URL_COUNTRIES = f"{BASE_URL}/export?format=csv&gid=0"          # 1番目のシート（48カ国勝敗）
URL_SETTINGS = f"{BASE_URL}/export?format=csv&gid=460959744"  # 2番目のシート（設定・コメント）
URL_ODDS = f"{BASE_URL}/export?format=csv&gid=1519733841"     # 3番目のシート（オッズ）

@st.cache_data(ttl=300)
def load_data():
    try:
        # 1. 48カ国の勝敗マスタを読み込み
        df_master = pd.read_csv(URL_COUNTRIES)
        
        # 強制的に整数型に変換（小数の混入を根本から防ぐ）
        df_master['勝ち数'] = pd.to_numeric(df_master['勝ち数'], errors='coerce').fillna(0).astype(int)
        df_master['分け数'] = pd.to_numeric(df_master['分け数'], errors='coerce').fillna(0).astype(int)
        df_master['負け数'] = pd.to_numeric(df_master['負け数'], errors='coerce').fillna(0).astype(int)
        df_master['オッズ'] = pd.to_numeric(df_master['オッズ'], errors='coerce').fillna(1).astype(int)
        
        # 日付と敗退判定
        df_master['生日付'] = df_master['日付'].fillna('').astype(str).str.strip()
        df_master['is_eliminated'] = df_master['生日付'].apply(lambda x: '×' in x or 'X' in x.upper())
        
        # 勝ち頭計算用のクレンジング
        df_master['表示日付'] = df_master['生日付'].apply(
            lambda x: x.upper().replace('D', '').replace('分', '').replace('△', '').strip()
        )
        df_master.loc[df_master['is_eliminated'], '表示日付'] = ''
        
        # ポイント計算
        df_master['勝ち点'] = df_master['勝ち数'] * 3 + df_master['分け数'] * 1
        df_master['ポイント'] = (df_master['オッズ'] * df_master['勝ち点']).astype(int)
        
        # 国名マッピング用の安全な辞書
        master_dict = {}
        for _, row in df_master.iterrows():
            c_name = str(row['国名']).strip()
            master_dict[c_name] = {
                'ポイント': int(row['ポイント']),
                'オッズ': int(row['オッズ']),
                'is_eliminated': row['is_eliminated']
            }
            
        # 2. オッズデータの読み込み（完全に独立して処理）
        df_odds_raw = pd.read_csv(URL_ODDS)
        df_odds_raw['参加者'] = df_odds_raw['参加者'].fillna('').astype(str).str.strip()
        df_odds_raw = df_odds_raw[df_odds_raw['参加者'] != ''].reset_index(drop=True)
        
        # 1〜8の列を安全にクレンジング（小数を防ぐため、float型の nan や数値を文字列化）
        num_cols = [str(i) for i in range(1, 9)]
        for col in num_cols:
            if col in df_odds_raw.columns:
                df_odds_raw[col] = df_odds_raw[col].fillna('').astype(str).str.strip()
                # 万が一 '13.0' などの表記になってしまった場合の対策
                df_odds_raw[col] = df_odds_raw[col].apply(lambda x: x[:-2] if x.endswith('.0') else x)
            else:
                df_odds_raw[col] = ''
                
        # 元の安定版と同じ集計用縦並びデータを100%安全に作成
        melted_rows = []
        for _, row in df_odds_raw.iterrows():
            p_name = row['参加者']
            for col in num_cols:
                c_name = row[col]
                if c_name and c_name != 'nan' and c_name != '':
                    melted_rows.append({'参加者': p_name, '国名': c_name})
        df_odds_melted = pd.DataFrame(melted_rows)
        
        # 3. 設定データの読み込み
        settings = {'my_comment': ''}
        try:
            sett_df = pd.read_csv(URL_SETTINGS)
            if not sett_df.empty and len(sett_df.columns) >= 2:
                col_comment = sett_df.columns[1]
                all_comments = sett_df[col_comment].dropna().astype(str).tolist()
                if all_comments:
                    settings['my_comment'] = "\n\n".join(all_comments)
        except:
            pass
            
        unique_dates = [d for d in df_master['表示日付'].unique() if d != '']
        def parse_date_key(date_str):
            try:
                m, d = map(int, date_str.split('/'))
                return (m, d)
            except:
                return (0, 0)
        date_list = sorted(unique_dates, key=parse_date_key)
        
        return df_master, df_odds_raw, df_odds_melted, master_dict, settings, date_list
    except Exception as e:
        st.error(f"データ読込失敗: {e}")
        return None, None, None, None, None, None

df_master, df_odds_raw, df_odds_melted, master_dict, settings, date_list = load_data()

# 特定日の獲得ポイントマップ
def get_daily_points_dict(dt, df_master_data):
    day_countries = df_master_data[df_master_data['表示日付'] == dt]
    pts_dict = {}
    for _, row in day_countries.iterrows():
        raw_date_upper = row['生日付'].upper()
        match_pt = 1 if ('D' in raw_date_upper or '分' in raw_date_upper or '△' in raw_date_upper) else 3
        pts_dict[row['国名']] = int(match_pt * row['オッズ'])
    return pts_dict

# 勝ち頭サマリー計算
def get_day_summary(dt, df_odds_melted_data, df_master_data):
    winner_str = "該当なし"
    hit_countries_str = "なし"
    day_pts_dict = get_daily_points_dict(dt, df_master_data)
    
    if day_pts_dict and not df_odds_melted_data.empty:
        player_day_pts = {}
        for _, row in df_odds_melted_data.iterrows():
            player = row['参加者']
            c_name = row['国名']
            if c_name in day_pts_dict:
                player_day_pts[player] = player_day_pts.get(player, 0) + day_pts_dict[c_name]
                
        if player_day_pts:
            max_pt = max(player_day_pts.values())
            top_players = [p for p, pt in player_day_pts.items() if pt == max_pt]
            
            formatted_players = [f"🏆 {p} さん" if i == 0 else f"👥 {p} さん" for i, p in enumerate(top_players)]
            winner_str = "、".join(formatted_players) + f" (+{int(max_pt)} pt)"
            
            leader = top_players[0]
            leader_hit = df_odds_melted_data[(df_odds_melted_data['参加者'] == leader) & (df_odds_melted_data['国名'].isin(day_pts_dict))]['国名'].tolist()
            if leader_hit:
                hit_countries_str = "、".join(leader_hit)
                
    return f"**【勝ち頭】** {winner_str}  \n**【勝ち頭のオッズした国】** {hit_countries_str}"

if df_master is not None and not df_master.empty:
    st.title("🏆 W杯サッカーくじ集計システム")
    st.write("---")
    
    # ==========================================
    # 📢 今日の勝ち頭 ＆ 管理人コメントエリア
    # ==========================================
    col_history, col_my = st.columns(2)
    with col_history:
        st.subheader("📅 今日の勝ち頭（2日分）")
        if date_list:
            latest_dates = date_list[-2:]
            latest_dates.reverse()
            for idx, dt in enumerate(latest_dates):
                summary_text = get_day_summary(df_odds_melted, df_master)
                if idx == 0:
                    st.info(f"🟢 **本日分 ({dt})** \n{summary_text}")
                else:
                    st.write(f"⚪ **昨日分 ({dt})** \n{summary_text}")
                    st.write("---")
        else:
            st.info("日付が入力されると自動表示されます。")
            
    with col_my:
        st.subheader("💬 管理人コメント欄")
        if settings and settings['my_comment']:
            st.success(settings['my_comment'].replace('\n', '  \n'))
        else:
            st.success("コメントはありません。")
            
    st.write("---")

    # ==========================================
    # 1. 参加者ランキング（完全復旧・整数表示）
    # ==========================================
    st.header("📊 参加者ランキング")
    if not df_odds_melted.empty:
        latest_date_str = date_list[-1] if date_list else "当日"
        today_col_name = f"{latest_date_str} ポイント"
        
        # 総ポイント計算
        ranking_df = pd.merge(df_odds_melted, df_master[['国名', 'ポイント']], on='国名', how='left')
        ranking_df['ポイント'] = ranking_df['ポイント'].fillna(0).astype(int)
        res_df = ranking_df.groupby('参加者')['ポイント'].sum().reset_index()
        res_df.columns = ['参加者', '総ポイント']
        
        # 当日ポイント計算
        latest_day_map = get_daily_points_dict(date_list[-1], df_master) if date_list else {}
        df_odds_melted['当日点'] = df_odds_melted['国名'].map(latest_day_map).fillna(0).astype(int)
        today_df = df_odds_melted.groupby('参加者')['当日点'].sum().reset_index()
        today_df.columns = ['参加者', today_col_name]
        
        # ドッキング
        final_ranking = pd.merge(res_df, today_df, on='参加者', how='left')
        final_ranking['総ポイント'] = final_ranking['総ポイント'].astype(int)
        final_ranking[today_col_name] = final_ranking[today_col_name].fillna(0).astype(int)
        
        # 収支計算
        average_point = final_ranking['総ポイント'].mean() if len(final_ranking) > 0 else 0
        final_ranking['収支ポイント'] = final_ranking['総ポイント'] - average_point
        final_ranking['収支ポイント'] = final_ranking['収支ポイント'].round(1)
        
        final_ranking = final_ranking.sort_values(by='総ポイント', ascending=False).reset_index(drop=True)
        final_ranking = final_ranking[['参加者', '総ポイント', today_col_name, '収支ポイント']]
        
        st.dataframe(final_ranking, use_container_width=True)
        st.caption(f"（※現在の実際の参加者平均ポイント: {average_point:.1f} pt）")

    st.write("---")

    # ==========================================
    # 📋 ⭐【完全独立・新設】オッズ国ステータス一覧
    # ==========================================
    st.header("📋 オッズ国ステータス一覧")
    if not df_odds_raw.empty:
        # スプレッドシートそのままの「参加者」と「1〜8」の列のみを安全に抽出
        status_cols = ['参加者'] + [str(i) for i in range(1, 9)]
        status_display_df = df_odds_raw[status_cols].copy()
        
        # マス目単位で「×」の国だけをピンポイントでグレーアウトする関数
        def style_cells(val):
            cleaned_val = str(val).strip()
            if cleaned_val in master_dict:
                if master_dict[cleaned_val]['is_eliminated']:
                    # 脱落した国をグレーアウト
                    return 'background-color: #f0f2f6; color: #a3a8b4; font-weight: normal; text-decoration: line-through;'
            return ''

        styled_status_df = status_display_df.style.applymap(style_cells, subset=[str(i) for i in range(1, 9)])
        st.dataframe(styled_status_df, use_container_width=True, hide_index=True)

    st.write("---")

    # ==========================================
    # 2. 各国の詳細 data 一覧
    # ==========================================
    st.header("⚽ 全48カ国 ステータス一覧")
    
    # オッズした人の文字列結合
    df_owners = df_odds_melted.groupby('国名')['参加者'].apply(lambda x: ', '.join(dict.fromkeys(x))).reset_index()
    df_owners.columns = ['国名', 'オッズした人']
    
    df_final_show = pd.merge(df_master, df_owners, on='国名', how='left')
    df_final_show['オッズした人'] = df_final_show['オッズした人'].fillna('—（未選択）')
    
    show_df = df_final_show[['グループ', '国名', 'ポイント', 'オッズした人', 'オッズ', '勝ち数', '分け数', '負け数', '日付', '勝ち点', 'is_eliminated']]
    show_df = show_df.sort_values(by=['グループ', '国名']).reset_index(drop=True)

    def style_eliminated_countries(row):
        if row['is_eliminated']:
            return ['background-color: #f0f2f6; color: #a3a8b4;'] * len(row)
        return [''] * len(row)

    styled_df = show_df.style.apply(style_eliminated_countries, axis=1)
    st.dataframe(
        styled_df, 
        use_container_width=True, 
        hide_index=True,
        column_order=['グループ', '国名', 'ポイント', 'オッズした人', 'オッズ', '勝ち数', '分け数', '負け数', '日付', '勝ち点']
    )
