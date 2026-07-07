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
        
        # すべて整数（int）として確実にキャスト
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
        
        # 勝ち頭の履歴計算用（×やDを排除した純粋な日付文字列を作る）
        df_master['表示日付'] = df_master['生日付'].apply(
            lambda x: x.upper().replace('D', '').replace('分', '').replace('△', '').strip()
        )
        # 敗退マーク（×）のみのセルは、日付リストから除外するために空欄にする
        df_master.loc[df_master['is_eliminated'], '表示日付'] = ''
        
        df_master['勝ち点'] = df_master['勝ち数'] * 3 + df_master['分け数'] * 1
        df_master['ポイント'] = df_master['オッズ'] * df_master['勝ち点']
        df_master['ポイント'] = df_master['ポイント'].astype(int)
        
        # 2. 参加者のオッズデータを読み込み
        try:
            df_odds = pd.read_csv(URL_ODDS)
            df_odds['参加者'] = df_odds['参加者'].fillna('未選択').astype(str).str.strip()
            df_odds['国名'] = df_odds['国名'].astype(str).str.strip()
        except:
            df_odds = pd.DataFrame(columns=['参加者', '国名'])
            
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
            
        return df_master, df_odds, settings, date_list
    except Exception as e:
        st.error(f"データの読み込みに失敗しました: {e}")
        return None, None, None, None

df_master, df_odds, settings, date_list = load_data()

# 特定の日の「その日単体」の獲得ポイントマップを計算する関数
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

# 特定の日の勝ち頭テキストを計算するヘルパー関数
def get_day_summary(dt, df_odds_data, df_master_data):
    day_pts_dict = get_daily_points_dict(dt, df_master_data)
    
    if not day_pts_dict or df_odds_data.empty:
        return "**【勝ち頭】** 該当なし  \n**【勝ち頭のオッズした国】** なし"
        
    # 1. 参加者ごとのその日の合計点を計算
    player_day_pts = {}
    player_hit_countries = {} # 各人がどの国を当てたかも記録
    
    for idx, row in df_odds_data.iterrows():
        player = row['参加者']
        c_name = row['国名']
        if c_name in day_pts_dict:
            player_day_pts[player] = player_day_pts.get(player, 0) + day_pts_dict[c_name]
            if player not in player_hit_countries:
                player_hit_countries[player] = []
            player_hit_countries[player].append(c_name)
            
    if not player_day_pts:
        return "**【勝ち頭】** 該当なし  \n**【勝ち頭のオッズした国】** なし"
        
    max_pt = max(player_day_pts.values())
    top_players = [p for p, pt in player_day_pts.items() if pt == max_pt]
    
    # 2. 国ごとにグループ分けして綺麗にテキスト化する
    # 例: {"ベルギー": ["高野連", "女神"], "スペイン": ["神"]}
    country_groups = {}
    all_hit_countries = set()
    
    for p in top_players:
        countries = sorted(player_hit_countries.get(p, []))
        c_key = "、".join(countries)
        if c_key not in country_groups:
            country_groups[c_key] = []
        country_groups[c_key].append(p)
        for c in countries:
            all_hit_countries.add(c)
            
    # テキストの組み立て
    winner_lines = []
    is_first = True
    for c_key, players in country_groups.items():
        p_strs = []
        for p in players:
            if is_first:
                p_strs.append(f"🏆 {p} さん")
                is_first = False
            else:
                p_strs.append(f"👥 {p} さん")
        winner_lines.append(f"{'、'.join(p_strs)} ({c_key}: +{int(max_pt)} pt)")
        
    winner_str = "  \n&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;".join(winner_lines)
    hit_countries_str = "、".join(sorted(list(all_hit_countries)))
    
    return f"**【勝ち頭】** {winner_str}  \n**【勝ち頭のオッズした国】** {hit_countries_str}"

if df_master is None or df_master.empty:
    st.warning("⚠️ スプレッドシートのデータが正しく読み込めませんでした。")
else:
    st.title("🏆 W杯サッカーくじ集計システム")
    
    # 🔄 キャッシュクリア＆最新データ更新ボタン
    if st.button("🔄 最新データに更新する（キャッシュクリア）", type="primary"):
        st.cache_data.clear()
        st.rerun()
        
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
                summary_text = get_day_summary(dt, df_odds, df_master)
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
    # 1. 参加者ランキング
    # ==========================================
    st.header("📊 参加者ランキング")
    if not df_odds.empty and len(df_odds) > 0:
        latest_date_str = date_list[-1] if date_list else "当日"
        today_col_name = f"{latest_date_str} ポイント"
        
        df_player_points = pd.merge(df_odds, df_master[['国名', 'ポイント']], on='国名', how='left')
        df_player_points['ポイント'] = df_player_points['ポイント'].fillna(0).astype(int)
        
        ranking_df = df_player_points.groupby('参加者')['ポイント'].sum().reset_index()
        ranking_df.columns = ['参加者', '総ポイント']
        
        df_today_points = pd.DataFrame(columns=['参加者', today_col_name])
        if date_list:
            latest_date = date_list[-1]
            latest_day_map = get_daily_points_dict(latest_date, df_master)
            
            player_today_list = []
            for _, row in df_odds.iterrows():
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
        st.info("「オッズ」シートに参加者のデータが入力されると、ここにランキングが表示されます。")

    # ==========================================
    # 2. 各国の詳細 data 一覧
    # ==========================================
    st.header("⚽ 全48カ国 ステータス一覧")
    if not df_odds.empty:
        df_owners = df_odds.groupby('国名')['参加者'].apply(lambda x: ', '.join(x)).reset_index()
        df_owners.columns = ['国名', 'オッズした人']
        df_final_show = pd.merge(df_master, df_owners, on='国名', how='left')
    else:
        df_final_show = df_master.copy()
        df_final_show['オッズした人'] = '—（未選択）'
        
    df_final_show['オッズした人'] = df_final_show['オッズした人'].fillna('—（未選択）')
    
    show_df = df_final_show[['グループ', '国名', 'ポイント', 'オッズした人', 'オッズ', '勝ち数', '分け数', '負け数', '日付', '勝ち点', 'is_eliminated']]
    
    # 昇順ソート
    show_df = show_df.sort_values(by=['グループ', '国名']).reset_index(drop=True)

    # 日付欄に「×」が入っている行をグレーアウトするスタイリング関数
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
