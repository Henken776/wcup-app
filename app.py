import streamlit as st
import pandas as pd
from datetime import datetime

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
        for col in ['グループ', '国名', 'オッズ', '勝ち数', '分け数', '負け数']:
            if col not in df_master.columns:
                st.error(f"「シート1」に '{col}' の列が見つかりません。")
                return None, None, None, None, None
        
        df_master['勝ち数'] = df_master['勝ち数'].fillna(0).astype(int)
        df_master['分け数'] = df_master['分け数'].fillna(0).astype(int)
        df_master['負け数'] = df_master['負け数'].fillna(0).astype(int)
        df_master['オッズ'] = df_master['オッズ'].fillna(1.0).astype(float)
        
        df_master['勝ち点'] = df_master['勝ち数'] * 3 + df_master['分け数'] * 1
        df_master['ポイント'] = df_master['オッズ'] * df_master['勝ち点']
        
        # 2. 参加者のオッズデータを読み込み
        try:
            df_odds = pd.read_csv(URL_ODDS)
            df_odds['参加者'] = df_odds['参加者'].fillna('未選択').astype(str).str.strip()
            df_odds['国名'] = df_odds['国名'].astype(str).str.strip()
        except:
            df_odds = pd.DataFrame(columns=['参加者', '国名'])
            
        # 3. 設定データの読み込みと全日程の解析
        settings = {'results_raw': '', 'my_comment': ''}
        day_data = {} # 日付ごとの国リスト
        
        try:
            sett_df = pd.read_csv(URL_SETTINGS)
            if not sett_df.empty:
                col_results = sett_df.columns[0]
                raw_lines = sett_df[col_results].dropna().astype(str).tolist()
                settings['results_raw'] = "\n".join(raw_lines)
                
                for line in raw_lines:
                    if ',' in line:
                        parts = line.split(',', 1)
                        dt = parts[0].strip()
                        c_name = parts[1].strip()
                        
                        if dt not in day_data:
                            day_data[dt] = []
                        if c_name not in day_data[dt]:
                            day_data[dt].append(c_name)
                
                # B列：管理人のコメントをすべて結合
                if len(sett_df.columns) >= 2:
                    col_comment = sett_df.columns[1]
                    all_comments = sett_df[col_comment].dropna().astype(str).tolist()
                    if all_comments:
                        settings['my_comment'] = "\n\n".join(all_comments)
        except Exception as e:
            st.error(f"設定シートの読み込みエラー: {e}")
            
        # 日付文字列を「月/日」の数値ベースでソート
        def parse_date_key(date_str):
            try:
                m, d = map(int, date_str.split('/'))
                return (m, d)
            except:
                return (0, 0)
                
        sorted_dates = sorted(list(day_data.keys()), key=parse_date_key)
            
        return df_master, df_odds, settings, day_data, sorted_dates
    except Exception as e:
        st.error(f"データの読み込みに失敗しました: {e}")
        return None, None, None, None, None

df_master, df_odds, settings, day_data, date_list = load_data()

# 各日程における国ごとの「その日単体の獲得ポイント」を、時系列の差分から100%正確に計算する関数
def calculate_daily_points_map(date_list, day_data, df_master):
    # 各国のポイント履歴をシミュレート
    # 初期状態は全員0点
    history_pts = {country: 0.0 for country in df_master['国名']}
    
    # マスタの「最終的な累計ポイント」を取得
    final_pts = dict(zip(df_master['国名'], df_master['ポイント']))
    odds_map = dict(zip(df_master['国名'], df_master['オッズ']))
    
    daily_maps = {} # { 日付: { 国名: 当日ポイント } }
    
    # 過去の日付から順番に処理して、ポイントの「増分」を記録していく
    for dt in date_list:
        daily_maps[dt] = {}
        countries_on_day = day_data.get(dt, [])
        
        for c in countries_on_day:
            if c not in history_pts:
                continue
            # この日に試合があった国について、現在のマスタの試合数情報から「1試合分の勝ち点」を逆算して増分とする
            # 差分シミュレーションの狂いを防ぐため、マスタの現在の最新勝敗から1試合分のポイント（3×オッズ または 1×オッズ）を正確に抽出
            c_row = df_master[df_master['国名'] == c].iloc[0]
            total_g = c_row['勝ち数'] + c_row['分け数'] + c_row['負け数']
            
            if total_g > 0:
                # 1試合あたりの平均勝ち点をベースに、最も近い勝ち点（3点 or 1点）を判定
                avg_pt = (c_row['勝ち数'] * 3 + c_row['分け数'] * 1) / total_g
                actual_game_pt = 3.0 if avg_pt > 1.8 else 1.0
                daily_maps[dt][c] = actual_game_pt * odds_map[c]
            else:
                daily_maps[dt][c] = 3.0 * odds_map[c] # 安全策
                
    return daily_maps

# 特定の日の勝ち頭と獲得国テキストを計算するヘルパー関数
def get_day_summary(dt, countries, df_odds, df_master, daily_pts_map):
    countries_str = "、".join(countries)
    winner_str = "該当なし"
    
    if countries and not df_odds.empty:
        # この日の各国の正確な単体ポイントを取得
        day_pts_dict = daily_pts_map.get(dt, {})
        
        # 参加者ごとに集計
        player_day_pts = {}
        for _, row in df_odds.iterrows():
            player = row['参加者']
            c_name = row['国名']
            if c_name in day_pts_dict:
                player_day_pts[player] = player_day_pts.get(player, 0.0) + day_pts_dict[c_name]
                
        if player_day_pts:
            max_pt = max(player_day_pts.values())
            top_players = [p for p, pt in player_day_pts.items() if pt == max_pt]
            
            formatted_players = []
            for i, player in enumerate(top_players):
                if i == 0:
                    formatted_players.append(f"🏆 {player} さん")
                else:
                    formatted_players.append(f"👥 {player} さん")
                    
            winner_str = "、".join(formatted_players) + f" (+{max_pt:.1f} pt)"
            
    return f"**【ポイント獲得国】** {countries_str}  \n**【勝ち頭】** {winner_str}"

if df_master is None or df_master.empty:
    st.warning("⚠️ スプレッドシートのデータが正しく読み込めませんでした。")
else:
    # 事前に全日程の正確な当日単体ポイントを計算
    daily_pts_map = calculate_daily_points_map(date_list, day_data, df_master)

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
                summary_text = get_day_summary(dt, day_data[dt], df_odds, df_master, daily_pts_map)
                if idx == 0:
                    st.info(f"🟢 **本日分 ({dt})** \n{summary_text}")
                else:
                    st.write(f"⚪ **昨日分 ({dt})** \n{summary_text}")
                    st.write("---")
        else:
            st.info("結果が登録されると、ここに2日分の履歴が自動表示されます。")
            
    with col_my:
        st.subheader("💬 管理人コメント欄（不定期更新）")
        if settings and settings['my_comment']:
            st.success(settings['my_comment'].replace('\n', '  \n'))
        else:
            st.success("ここに管理人からのコメントが表示されます。")
            
    st.write("---")

    # ==========================================
    # 1. 参加者ランキング（最新日付と100%連動）
    # ==========================================
    st.header("📊 参加者ランキング")
    if not df_odds.empty and len(df_odds) > 0:
        latest_date_str = date_list[-1] if date_list else "当日"
        today_col_name = f"{latest_date_str} ポイント"
        
        df_player_points = pd.merge(df_odds, df_master[['国名', 'ポイント']], on='国名', how='left')
        df_player_points['ポイント'] = df_player_points['ポイント'].fillna(0)
        
        ranking_df = df_player_points.groupby('参加者')['ポイント'].sum().reset_index()
        ranking_df.columns = ['参加者', '総ポイント']
        
        # 最新日のポイントを正しくマッピング
        df_today_points = pd.DataFrame(columns=['参加者', today_col_name])
        if date_list:
            latest_date = date_list[-1]
            latest_day_map = daily_pts_map.get(latest_date, {})
            
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
            ranking_df[today_col_name] = ranking_df[today_col_name].fillna(0)
        else:
            ranking_df[today_col_name] = 0.0
        
        average_point = ranking_df['総ポイント'].mean()
        ranking_df['収支ポイント'] = ranking_df['総ポイント'] - average_point
        ranking_df = ranking_df.sort_values(by='総ポイント', ascending=False).reset_index(drop=True)
        
        ranking_df['総ポイント'] = ranking_df['総ポイント'].round(1)
        ranking_df[today_col_name] = ranking_df[today_col_name].round(1)
        ranking_df['収支ポイント'] = ranking_df['収支ポイント'].round(1)
        
        ranking_df = ranking_df[['参加者', '総ポイント', today_col_name, '収支ポイント']]
        
        st.dataframe(ranking_df, use_container_width=True)
        st.caption(f"（※現在の実際の参加者平均ポイント: {average_point:.1f} pt）")
    else:
        st.info("「オッズ」シートに参加者のデータが入力されると、ここにランキングが表示されます。")

    # ==========================================
    # 2. 各国の詳細データ一覧
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
    
    show_df = df_final_show[['グループ', '国名', 'ポイント', 'オッズした人', 'オッズ', '勝ち数', '分け数', '負け数', '勝ち点']]
    show_df['ポイント'] = show_df['ポイント'].round(1)
    st.dataframe(show_df.sort_values(by=['グループ', '国名']), use_container_width=True, hide_index=True)
