import streamlit as st
import pandas as pd

st.set_page_config(page_title="W杯サッカーくじ集計システム", layout="wide")

# スプレッドシートのベースURL
BASE_URL = "https://docs.google.com/spreadsheets/d/1_vlPH_Yl5zYKT4-5p5POZZLM1cJPbYwQ0yzUjF0FinA"

# 各シートのID（固定）
URL_COUNTRIES = f"{BASE_URL}/export?format=csv&gid=0"          # 1番目のシート（48カ国のマスタ勝敗）
URL_SETTINGS = f"{BASE_URL}/export?format=csv&gid=460959744"  # 2番目のシート（設定・コメント）
URL_ODDS = f"{BASE_URL}/export?format=csv&gid=1519733841"     # 3番目のシート（オッズ）

@st.cache_data(ttl=300)
def load_data():
    try:
        # 1. 48カ国の勝敗マスタを読み込み
        df_master = pd.read_csv(URL_COUNTRIES)
        
        for col in ['グループ', '国名', 'オッズ', '勝ち数', '分け数', '負け数', '日付']:
            if col not in df_master.columns:
                st.error(f"「シート1」に '{col}' の列が見つかりません。")
                return None, None, None, None
        
        # すべて整数（int）として確実に固定
        df_master['勝ち数'] = df_master['勝ち数'].fillna(0).astype(int)
        df_master['分け数'] = df_master['分け数'].fillna(0).astype(int)
        df_master['負け数'] = df_master['負け数'].fillna(0).astype(int)
        df_master['オッズ'] = df_master['オッズ'].fillna(1).astype(int)
        
        # 日付・敗退判定のパース処理
        df_master['生日付'] = df_master['日付'].fillna('').astype(str).str.strip()
        
        # 大文字小文字の「X」や「×」が含まれているかチェック
        df_master['is_eliminated'] = df_master['生日付'].apply(
            lambda x: '×' in x or 'X' in x.upper()
        )
        
        # 勝ち頭の履歴計算用
        df_master['表示日付'] = df_master['生日付'].apply(
            lambda x: x.upper().replace('D', '').replace('分', '').replace('△', '').strip()
        )
        df_master.loc[df_master['is_eliminated'], '表示日付'] = ''
        
        df_master['勝ち点'] = df_master['勝ち数'] * 3 + df_master['分け数'] * 1
        df_master['ポイント'] = df_master['オッズ'] * df_master['勝ち点']
        df_master['ポイント'] = df_master['ポイント'].astype(int)
        
        # 2. 参加者のオッズデータを読み込み（画像通りの横型マスタとして保持）
        try:
            df_odds_raw = pd.read_csv(URL_ODDS)
            df_odds_raw['参加者'] = df_odds_raw['参加者'].fillna('').astype(str).str.strip()
            df_odds_raw = df_odds_raw[df_odds_raw['参加者'] != '']
            
            # ランキング計算用に、内部処理用の縦並びデータも作成
            melted_rows = []
            num_cols = [str(i) for i in range(1, 9)]
            for col in num_cols:
                if col in df_odds_raw.columns:
                    for _, row in df_odds_raw.iterrows():
                        c_name = str(row[col]).strip()
                        if c_name and c_name != 'nan' and c_name != '':
                            melted_rows.append({'参加者': row['参加者'], '国名': c_name})
            df_odds_melted = pd.DataFrame(melted_rows)
        except Exception as e:
            st.error(f"オッズシートの読み込みに失敗しました: {e}")
            df_odds_raw = pd.DataFrame(columns=['参加者', '1', '2', '3', '4', '5', '6', '7', '8'])
            df_odds_melted = pd.DataFrame(columns=['参加者', '国名'])
            
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
            
        return df_master, df_odds_raw, df_odds_melted, settings, date_list
    except Exception as e:
        st.error(f"データの読み込みに失敗しました: {e}")
        return None, None, None, None, None

df_master, df_odds_raw, df_odds_melted, settings, date_list = load_data()

# 特定の日の獲得ポイントマップを計算
def get_daily_points_dict(dt, df_master_data):
    day_countries = df_master_data[df_master_data['表示日付'] == dt]
    pts_dict = {}
    for _, row in day_countries.iterrows():
        raw_date_upper = row['生日付'].upper()
        if 'D' in raw_date_upper or '分' in raw_date_upper or '△' in raw_date_upper:
            match_pt = 1
        else:
            match_pt = 3
        pts_dict[row['国名']] = int(match_pt * row['オッズ'])
    return pts_dict

# 特定の日の勝ち頭テキストを計算
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
            
            formatted_players = []
            for i, player in enumerate(top_players):
                if i == 0:
                    formatted_players.append(f"🏆 {player} さん")
                else:
                    formatted_players.append(f"👥 {player} さん")
            winner_str = "、".join(formatted_players) + f" (+{int(max_pt)} pt)"
            
            leader = top_players[0]
            leader_odds_countries = df_odds_melted_data[df_odds_melted_data['参加者'] == leader]['国名'].tolist()
            leader_hit_countries = [c for c in leader_odds_countries if c in day_pts_dict]
            if leader_hit_countries:
                hit_countries_str = "、".join(leader_hit_countries)
            
    return f"**【勝ち頭】** {winner_str}  \n**【勝ち頭のオッズした国】** {hit_countries_str}"

if df_master is None or df_master.empty:
    st.warning("⚠️ スプレッドシートのデータが正しく読み込めませんでした。")
else:
    st.title("🏆 W杯サッカーくじ集計システム")
    st.write("---")
    
    # ==========================================
    # 📢 今日の勝ち頭（2日分） ＆ 管理人コメントエリア
    # ==========================================
    col_history, col_my = st.columns(2)
    
    with col_history:
        st.subheader("📅 今日の勝ち頭（2日分）")
        if date_list:
            latest_dates = date_list[-2:]
            latest_dates.reverse()
            for idx, dt in enumerate(latest_dates):
                summary_text = get_day_summary(dt, df_odds_melted, df_master)
                if idx == 0:
                    st.info(f"🟢 **本日分 ({dt})** \n{summary_text}")
                else:
                    st.write(f"⚪ **昨日分 ({dt})** \n{summary_text}")
                    st.write("---")
        else:
            st.info("シート1の「日付」列に日付が入力されると、ここに自動表示されます。")
            
    with col_my:
        st.subheader("💬 管理人コメント欄（不定期更新）")
        if settings and settings['my_comment']:
            st.success(settings['my_comment'].replace('\n', '  \n'))
        else:
            st.success("ここに管理人からのコメントが表示されます。")
            
    st.write("---")

    # ==========================================
    # 1. 参加者ランキング（完全元通り・整数表示）
    # ==========================================
    st.header("📊 参加者ランキング")
    if not df_odds_melted.empty and len(df_odds_melted) > 0:
        latest_date_str = date_list[-1] if date_list else "当日"
        today_col_name = f"{latest_date_str} ポイント"
        
        df_player_points = pd.merge(df_odds_melted, df_master[['国名', 'ポイント']], on='国名', how='left')
        df_player_points['ポイント'] = df_player_points['ポイント'].fillna(0).astype(int)
        
        ranking_df = df_player_points.groupby('参加者')['ポイント'].sum().reset_index()
        ranking_df.columns = ['参加者', '総ポイント']
        
        df_today_points = pd.DataFrame(columns=['参加者', today_col_name])
        if date_list:
            latest_date = date_list[-1]
            latest_day_map = get_daily_points_dict(latest_date, df_master)
            
            player_today_list = []
            for _, row in df_odds_melted.iterrows():
                player = row['参加者']
                c_name = row['国名']
                if c_name in latest_day_map:
                    player_today_list.append({'参加者': player, '当日点': latest_day_map[c_name]})
            
            if player_today_list:
                df_temp = pd.DataFrame(player_today_list)
                df_today_points = df_temp.groupby('参加者')['当日点'].sum().reset_index()
                df_today_points.columns = ['参加者', today_col_name]

        if not df_today_points.empty:
            ranking_df = pd.merge(ranking_df, df_today_points, on='参加者', how='left')
            ranking_df[today_col_name] = ranking_df[today_col_name].fillna(0).astype(int)
        else:
            ranking_df[today_col_name] = 0
            
        ranking_df['総ポイント'] = ranking_df['総ポイント'].astype(int)
        ranking_df[today_col_name] = ranking_df[today_col_name].astype(int)
        
        average_point = ranking_df['総ポイント'].mean()
        ranking_df['収支ポイント'] = ranking_df['総ポイント'] - average_point
        ranking_df['収支ポイント'] = ranking_df['収支ポイント'].round(1)
        
        ranking_df = ranking_df.sort_values(by='総ポイント', ascending=False).reset_index(drop=True)
        ranking_df = ranking_df[['参加者', '総ポイント', today_col_name, '収支ポイント']]
        
        st.dataframe(ranking_df, use_container_width=True)
        st.caption(f"（※現在の実際の参加者平均ポイント: {average_point:.1f} pt）")
    else:
        st.info("データを読み込み中、またはデータが空です。")

    st.write("---")

    # ==========================================
    # 📋 ⭐【新設】オッズ国ステータス一覧（ご
