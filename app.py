import flet as ft
import duckdb
import os

def main(page: ft.Page):
    # =======================================================
    # 1. 기획 및 미학 요건 설정 (화면 타이틀, 다크 테마)
    # =======================================================
    page.title = "로스트아크 원정대 스케줄러 (Lost Ark Expedition Scheduler)"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 30
    page.window_width = 1100
    page.window_height = 700

    # =======================================================
    # 2. DuckDB 데이터베이스 초기화 및 기본 세팅
    # =======================================================
    # 파일 기반 로컬 DB 연결 (실행 시 같은 폴더에 생성됨)
    con = duckdb.connect('lostark_scheduler.db')
    
    # 실습/테스트용 테이블 초기화
    con.execute("DROP TABLE IF EXISTS RaidSchedule;")
    con.execute("DROP TABLE IF EXISTS Character;")
    con.execute("DROP TABLE IF EXISTS Raid;")

    # 6단계 Logical Design에서 정의한 BCNF 규격의 테이블 스펙 생성
    con.execute("""
        CREATE TABLE Character (
            character_id INTEGER PRIMARY KEY,
            name VARCHAR NOT NULL UNIQUE,
            class_name VARCHAR NOT NULL,
            item_level DOUBLE NOT NULL,
            image_path VARCHAR NOT NULL
        );
    """)
    con.execute("""
        CREATE TABLE Raid (
            raid_id INTEGER PRIMARY KEY,
            raid_name VARCHAR NOT NULL UNIQUE,
            req_level DOUBLE NOT NULL,
            gold_reward INTEGER NOT NULL
        );
    """)
    con.execute("""
        CREATE TABLE RaidSchedule (
            schedule_id INTEGER PRIMARY KEY,
            character_id INTEGER REFERENCES Character(character_id),
            raid_id INTEGER REFERENCES Raid(raid_id),
            is_cleared BOOLEAN DEFAULT FALSE
        );
    """)

    # 마스터 데이터 (레이드 정보) 기입
    con.execute("INSERT INTO Raid VALUES (1, '일리아칸 하드', 1600.00, 7500);")
    con.execute("INSERT INTO Raid VALUES (2, '에키드나 노말', 1620.00, 14500);")
    con.execute("INSERT INTO Raid VALUES (3, '카멘 하드', 1630.00, 20000);")

    # 초기 샘플 데이터 기입 (이미지 주소 복구)
    con.execute("INSERT INTO Character VALUES (1, '바드대세오', '바드', 1620.00, 'https://cdn-lostark.game.onstove.com/2018/obt/assets/images/common/thumb/bard.png');")
    con.execute("INSERT INTO Character VALUES (2, '빵빵한슬레', '슬레이어', 1600.00, 'https://cdn-lostark.game.onstove.com/2018/obt/assets/images/common/thumb/berserker.png');")
    
    con.execute("INSERT INTO RaidSchedule VALUES (1, 1, 2, FALSE);") 
    con.execute("INSERT INTO RaidSchedule VALUES (2, 2, 1, TRUE);")

    # =======================================================
    # 3. 비즈니스 로직 및 컴포넌트 렌더링 함수 (JOIN 연산 포함)
    # =======================================================
    def refresh_dashboard():
        """ 3개 테이블을 JOIN하여 화면 우측 대시보드 리스트를 갱신하는 함수 """
        dashboard_view.controls.clear()
        
        # 7.1 단계 시퀀스 다이어그램과 연동되는 핵심 JOIN 쿼리
        join_query = """
            SELECT 
                c.character_id, c.name, c.class_name, c.item_level, c.image_path,
                r.raid_name, r.gold_reward, s.is_cleared, s.schedule_id
            FROM Character c
            LEFT JOIN RaidSchedule s ON c.character_id = s.character_id
            LEFT JOIN Raid r ON s.raid_id = r.raid_id
            ORDER BY c.item_level DESC;
        """
        rows = con.execute(join_query).fetchall()

        if not rows:
            dashboard_view.controls.append(ft.Text("등록된 캐릭터가 없습니다.", color="white54"))
            page.update()
            return

        # 캐릭터별로 데이터를 묶어서 카드 형태로 UI 빌드
        characters_dict = {}
        for row in rows:
            c_id, c_name, c_class, c_level, c_img, r_name, r_gold, is_cleared, s_id = row
            if c_id not in characters_dict:
                characters_dict[c_id] = {
                    "name": c_name, "class": c_class, "level": c_level, "img": c_img, "raids": []
                }
            if r_name: 
                characters_dict[c_id]["raids"].append({
                    "sched_id": s_id, "name": r_name, "gold": r_gold, "cleared": is_cleared
                })

        # 가공된 딕셔너리를 기반으로 Flet Card UI 동적 생성
        for char_id, info in characters_dict.items():
            raid_rows = []
            for rd in info["raids"]:
                def make_toggle_event(sid):
                    return lambda e: toggle_clear_status(sid, e.control.value)

                status_color = "green" if rd["cleared"] else "amber"
                
                raid_rows.append(
                    ft.Row([
                        ft.Checkbox(value=rd["cleared"], on_change=make_toggle_event(rd["sched_id"])),
                        ft.Text(f"{rd['name']} ({rd['gold']:,} G)", color=status_color, size=14),
                    ], alignment=ft.MainAxisAlignment.START)
                )

            if not raid_rows:
                raid_rows.append(ft.Text("배정된 주간 레이드 없음", size=13, color="white38"))

            def make_delete_event(cid):
                return lambda e: delete_character(cid)

            # DB에 저장된 이미지 경로가 비어있으면 기본 이미지 처리
            img_src = info["img"] if info["img"] else "https://cdn-lostark.game.onstove.com/2018/obt/assets/images/common/thumb/warrior.png"

            card = ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Row([
                                ft.Image(src=img_src, width=45, height=45, fit="contain"),
                                ft.Column([
                                    ft.Text(info["name"], size=16, weight=ft.FontWeight.BOLD),
                                    ft.Text(f"{info['class']} | Lv.{info['level']}", size=13, color="white70"),
                                ], spacing=2),
                            ], spacing=10),
                            ft.TextButton("삭제", style=ft.ButtonStyle(color="red400"), on_click=make_delete_event(char_id))
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Divider(height=10, color="white10"),
                        ft.Column(controls=raid_rows, spacing=5)
                    ]),
                    padding=15
                ),
                width=340
            )
            dashboard_view.controls.append(card)
        
        # 총 예상 수급 골드 출력 갱신 (Join 통계)
        total_gold = con.execute("""
            SELECT COALESCE(SUM(r.gold_reward), 0) 
            FROM RaidSchedule s 
            JOIN Raid r ON s.raid_id = r.raid_id 
            WHERE s.is_cleared = TRUE
        """).fetchone()[0]
        gold_status_text.value = f"이번 주 현재 정산 골드: {total_gold:,} G"
        
        # 드롭다운 메뉴 원정대 최신화
        update_dropdowns()
        page.update()

    # =======================================================
    # 4. 개별 CRUD CBM(Callback Method) 선언
    # =======================================================
    def toggle_clear_status(sched_id, current_value):
        con.execute("UPDATE RaidSchedule SET is_cleared = ? WHERE schedule_id = ?;", (current_value, sched_id))
        refresh_dashboard()

    def add_character_logic(e):
        if not txt_char_name.value or not txt_item_level.value:
            return
        
        img_mapping = {
            "바드": "https://cdn-lostark.game.onstove.com/2018/obt/assets/images/common/thumb/bard.png",
            "슬레이어": "https://cdn-lostark.game.onstove.com/2018/obt/assets/images/common/thumb/berserker.png",
            "도화가": "https://cdn-lostark.game.onstove.com/2018/obt/assets/images/common/thumb/artist.png"
        }
        selected_img = img_mapping.get(drp_class.value, "https://cdn-lostark.game.onstove.com/2018/obt/assets/images/common/thumb/warrior.png")

        try:
            next_id = con.execute("SELECT COALESCE(MAX(character_id), 0) + 1 FROM Character;").fetchone()[0]
            con.execute(
                "INSERT INTO Character VALUES (?, ?, ?, ?, ?);",
                (next_id, txt_char_name.value, drp_class.value, float(txt_item_level.value), selected_img)
            )
            txt_char_name.value = ""
            txt_item_level.value = "1600"
            refresh_dashboard()
        except Exception as ex:
            print(f"등록 실패 (중복 명칭 등): {ex}")

    def add_schedule_logic(e):
        if not drp_select_char.value or not drp_select_raid.value:
            return
        
        c_id = int(drp_select_char.value)
        r_id = int(drp_select_raid.value)

        c_level = con.execute("SELECT item_level FROM Character WHERE character_id = ?;", (c_id,)).fetchone()[0]
        r_level = con.execute("SELECT req_level FROM Raid WHERE raid_id = ?;", (r_id,)).fetchone()[0]

        if c_level < r_level:
            page.overlay.append(ft.SnackBar(ft.Text(f"입장 레벨이 부족합니다! (요구 레벨: {r_level})"), open=True))
            page.update()
            return

        next_sid = con.execute("SELECT COALESCE(MAX(schedule_id), 0) + 1 FROM RaidSchedule;").fetchone()[0]
        con.execute("INSERT INTO RaidSchedule VALUES (?, ?, ?, FALSE);", (next_sid, c_id, r_id))
        refresh_dashboard()

    def delete_character(char_id):
        """ Cascade 제약조건 부재를 보완하기 위해 자식 스케줄을 먼저 수동 삭제 후 부모 캐릭터 삭제 """
        con.execute("DELETE FROM RaidSchedule WHERE character_id = ?;", (char_id,))
        con.execute("DELETE FROM Character WHERE character_id = ?;", (char_id,))
        refresh_dashboard()

    def update_dropdowns():
        chars = con.execute("SELECT character_id, name FROM Character;").fetchall()
        drp_select_char.options = [ft.dropdown.Option(str(row[0]), row[1]) for row in chars]
        
        raids = con.execute("SELECT raid_id, raid_name FROM Raid;").fetchall()
        drp_select_raid.options = [ft.dropdown.Option(str(row[0]), row[1]) for row in raids]

    # =======================================================
    # 5. UI 컨트롤 컴포넌트 배치 정의 (UI Design 준수)
    # =======================================================
    txt_char_name = ft.TextField(label="캐릭터 닉네임", width=250)
    drp_class = ft.Dropdown(
        label="직업 클래스 선택",
        options=[ft.dropdown.Option("바드"), ft.dropdown.Option("슬레이어"), ft.dropdown.Option("도화가")],
        value="바드", width=250
    )
    txt_item_level = ft.TextField(label="아이템 레벨", value="1600", width=250)
    btn_add_char = ft.ElevatedButton("원정대 캐릭터 등록", icon="add", on_click=add_character_logic, width=250)

    drp_select_char = ft.Dropdown(label="대상 캐릭터 선택", width=250)
    drp_select_raid = ft.Dropdown(label="도전할 레이드 선택", width=250)
    btn_add_sched = ft.ElevatedButton("주간 레이드 스케줄 추가", icon="play_arrow", on_click=add_schedule_logic, width=250)

    gold_status_text = ft.Text("이번 주 현재 정산 골드: 0 G", size=18, color="gold", weight=ft.FontWeight.BOLD)
    
    # 동적 스크롤 및 배치 래핑이 구현된 핵심 대시보드 뷰 컴포넌트
    dashboard_view = ft.Row(wrap=True, spacing=20, scroll=ft.ScrollMode.AUTO, expand=True)

    # 전체 본문 레이아웃 조합 조립
    page.add(
        ft.Row([
            ft.Text("🛡️ 로스트아크 원정대 주간 레이드 매니저", size=26, weight=ft.FontWeight.BOLD),
            gold_status_text
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.Divider(height=15, color="white24"),
        ft.Row([
            # 좌측 컨트롤 패널 섹션
            ft.Container(
                content=ft.Column([
                    ft.Text("📌 신규 캐릭터 추가 폼", size=16, weight=ft.FontWeight.BOLD),
                    txt_char_name, drp_class, txt_item_level, btn_add_char,
                    ft.Container(height=15),
                    ft.Text("⚔️ 레이드 주간 일정 배정", size=16, weight=ft.FontWeight.BOLD),
                    drp_select_char, drp_select_raid, btn_add_sched
                ], spacing=12),
                padding=20,
                border=ft.Border.all(1, "white12"),
                border_radius=10,
                bgcolor="black26"
            ),
            # 우측 종합 대시보드 디스플레이 섹션 (★ 버그 수정: dashboard_view를 내부에 포함시킴)
            ft.Container(
                content=ft.Column([
                    ft.Text("📊 실시간 원정대 대시보드 (3개 테이블 실시간 JOIN 결과)", size=16, weight=ft.FontWeight.BOLD, color="blue"),
                    ft.Container(height=10),
                    dashboard_view  # <-- 이 부분이 누락되어 화면이 뜨지 않았었습니다.
                ], expand=True),
                expand=True,
                padding=10
            )
        ], alignment="start", vertical_alignment="start", expand=True)
    )

    # 최초 로드 시 데이터 뷰어 활성화 및 화면 강제 갱신
    refresh_dashboard()
    page.update()

if __name__ == "__main__":
    ft.app(target=main)